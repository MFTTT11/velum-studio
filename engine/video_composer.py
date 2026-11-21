"""Broadcast-Grade 1080p 60fps Cinematic Video Compositor (FFmpeg + OpenCV + LibASS).

Features:
- True 60fps subpixel Ken Burns zoom/pan (zero zoompan integer jitter)
- Alternating graded real photography & animated Netflix/Vox data plates (<=2.5s cuts)
- 0-2.0s high-contrast Shock Hook explosion + sub-bass/whoosh audio punch
- Live Telemetry HUD overlay (smooth progress rail, live metrics, timecode, watermark)
- Dark Netflix/Vox cinematic color grading (teal-obsidian shadow LUT + vignette + grain)
- Word-by-word kinetic scaling ASS captions synchronized to Whisper timestamps
- 3-stem cinema audio: cleaned narration + auto-ducked tension bed (`sidechaincompress`)
  + sample-accurate beat-synced SFX track, mastered via FFmpeg `loudnorm` (-14 LUFS)
"""

from __future__ import annotations

import math
import re
import subprocess
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from core.config import get_ffmpeg_bin, get_logger, load_brand_config, resolve_font
from engine.hud_renderer import render_data_plate, render_hud_overlay
from engine.media_fetcher import MediaFetcher
from engine.sfx_music_engine import SAMPLE_RATE, generate_audio_pack

logger = get_logger("video_composer")


def _apply_cinematic_grade(bgr: np.ndarray) -> np.ndarray:
    """Apply dark Netflix/Vox teal-obsidian color grade, S-curve contrast, and vignette."""
    img = bgr.astype(np.float32) / 255.0

    # Deepen exposure slightly for moody documentary contrast & HUD legibility
    img = np.clip(img * 0.78, 0.0, 1.0)
    # Gentle S-curve contrast boost
    img = np.clip(img * img * (3.0 - 2.0 * img) * 0.65 + img * 0.35, 0.0, 1.0)

    # Split-tone: cool deep teal-blue shadows, crisp warm amber highlights
    luma = 0.114 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.299 * img[:, :, 2]
    shadow_w = np.clip(1.0 - luma * 1.8, 0.0, 1.0)
    high_w = np.clip((luma - 0.45) * 1.8, 0.0, 1.0)

    # BGR channel adjustments
    img[:, :, 0] = np.clip(img[:, :, 0] + shadow_w * 0.055 - high_w * 0.025, 0.0, 1.0)  # B
    img[:, :, 1] = np.clip(img[:, :, 1] + shadow_w * 0.020 + high_w * 0.010, 0.0, 1.0)  # G
    img[:, :, 2] = np.clip(img[:, :, 2] - shadow_w * 0.022 + high_w * 0.045, 0.0, 1.0)  # R

    # Subtle radial vignette (never crushes edges to pure black to keep cropdetect clean)
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx / max(w - 1, 1) - 0.5) * 2.0
    ny = (yy / max(h - 1, 1) - 0.5) * 2.0
    dist2 = nx * nx + ny * ny
    vignette = np.clip(1.0 - 0.28 * (dist2**1.2), 0.58, 1.0)[:, :, None]
    img = img * vignette

    return np.clip(img * 255.0, 0, 255).astype(np.uint8)


def _ken_burns_frame(
    src_bgr: np.ndarray,
    out_w: int,
    out_h: int,
    progress: float,
    motion: str,
) -> np.ndarray:
    """Compute a silky-smooth subpixel affine Ken Burns zoom/pan frame at 60fps."""
    sh, sw = src_bgr.shape[:2]
    t = max(0.0, min(1.0, progress))
    # Smooth ease-in-out
    smooth_t = t * t * (3.0 - 2.0 * t)

    # Base scale guarantees full cover without black borders
    min_scale = max(out_w / sw, out_h / sh)
    if motion == "zoom_in":
        scale = min_scale * (1.03 + 0.09 * smooth_t)
        dx_frac, dy_frac = 0.0, 0.0
    elif motion == "zoom_out":
        scale = min_scale * (1.12 - 0.09 * smooth_t)
        dx_frac, dy_frac = 0.0, 0.0
    elif motion == "pan_right":
        scale = min_scale * 1.10
        dx_frac = -0.04 + 0.08 * smooth_t
        dy_frac = 0.0
    elif motion == "pan_left":
        scale = min_scale * 1.10
        dx_frac = 0.04 - 0.08 * smooth_t
        dy_frac = 0.0
    else:  # drift_up
        scale = min_scale * (1.06 + 0.05 * smooth_t)
        dx_frac = 0.0
        dy_frac = 0.035 - 0.07 * smooth_t

    cx = sw * 0.5 + sw * dx_frac
    cy = sh * 0.5 + sh * dy_frac

    # Clamp center so transformed image ALWAYS covers 100% of out_w x out_h
    half_w_in_src = (out_w * 0.5) / scale
    half_h_in_src = (out_h * 0.5) / scale
    cx = max(half_w_in_src + 1.0, min(sw - half_w_in_src - 1.0, cx))
    cy = max(half_h_in_src + 1.0, min(sh - half_h_in_src - 1.0, cy))

    tx = out_w * 0.5 - cx * scale
    ty = out_h * 0.5 - cy * scale
    mat = np.array([[scale, 0.0, tx], [0.0, scale, ty]], dtype=np.float32)

    return cv2.warpAffine(
        src_bgr,
        mat,
        (out_w, out_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def _prepare_hud_blend_cache(hud_rgba: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Precompute active HUD pixel mask and premultiplied BGR for ultra-fast 60fps compositing."""
    alpha = hud_rgba[:, :, 3]
    mask = alpha > 0
    a16 = alpha[mask].astype(np.uint16)[:, None]
    inv_a16 = (255 - a16)
    fg_premult = hud_rgba[mask][:, [2, 1, 0]].astype(np.uint16) * a16
    return mask, inv_a16, fg_premult


def _apply_hud_blend_fast(
    base_bgr: np.ndarray, mask: np.ndarray, inv_a16: np.ndarray, fg_premult: np.ndarray
) -> np.ndarray:
    """Blend HUD strictly onto non-transparent pixels (~5x faster than full-frame float32)."""
    out = base_bgr.copy()
    bg = out[mask].astype(np.uint16)
    out[mask] = ((bg * inv_a16 + fg_premult) >> 8).astype(np.uint8)
    return out


def _format_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - math.floor(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def build_kinetic_ass_subtitles(
    words: List[Dict[str, Any]],
    out_ass_path: Path,
    size: Tuple[int, int],
) -> Path:
    """Generate kinetic word-by-word scaling ASS subtitles (Signal Amber / Cyan highlights)."""
    w, h = size
    is_vertical = h > w

    # Resolve crisp bold font family name for libass across Windows and Ubuntu Linux
    font_path = resolve_font("headline").lower()
    if "bahnschrift" in font_path:
        font_name = "Bahnschrift"
    elif "robotocondensed" in font_path:
        font_name = "Roboto Condensed"
    elif "roboto" in font_path:
        font_name = "Roboto"
    elif "liberationsansnarrow" in font_path:
        font_name = "Liberation Sans Narrow"
    elif "liberationsans" in font_path:
        font_name = "Liberation Sans"
    elif "impact" in font_path:
        font_name = "Impact"
    elif "arial" in font_path:
        font_name = "Arial"
    else:
        font_name = "DejaVu Sans"
    font_size = 76 if is_vertical else 66
    margin_v = 360 if is_vertical else 76
    margin_lr = 64 if is_vertical else 120

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kinetic,{font_name},{font_size},&H00FAF7F4,&H0000B8FF,&H000F0907,&H9007090F,-1,0,0,0,100,100,1.5,0,1,6,3,2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Group words into punchy 3-word phrases (2 words if any word is long)
    groups: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    for word_item in words:
        token = word_item["word"].strip()
        if not token:
            continue
        cur.append(word_item)
        cur_chars = sum(len(x["word"]) for x in cur)
        ends_sentence = token.endswith((".", "!", "?", "—", ":"))
        if len(cur) >= 3 or cur_chars >= 18 or ends_sentence:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    lines: List[str] = [header]
    for grp in groups:
        for active_idx, active_w in enumerate(grp):
            start = float(active_w["start"])
            # Extend seamlessly to next word start to avoid caption flicker
            if active_idx + 1 < len(grp):
                end = max(start + 0.08, float(grp[active_idx + 1]["start"]))
            else:
                end = max(start + 0.12, float(active_w["end"]))

            parts: List[str] = []
            for j, w_obj in enumerate(grp):
                raw_txt = _escape_ass_text(w_obj["word"].upper())
                is_numeric = bool(re.search(r"\d|\$|%", raw_txt))
                if j == active_idx:
                    # Active spoken word: pop scale 118% -> 100% + Amber (or Cyan for numbers)
                    hi_col = "&H00FFE500&" if is_numeric else "&H0000B8FF&"
                    parts.append(
                        f"{{\\c{hi_col}\\fscx118\\fscy118\\t(0,95,\\fscx100\\fscy100)}}{raw_txt}{{\\r}}"
                    )
                else:
                    parts.append(f"{{\\c&H00FAF7F4&\\alpha&H20&}}{raw_txt}{{\\r}}")

            dialogue = (
                f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},"
                f"Kinetic,,0,0,0,,{' '.join(parts)}\n"
            )
            lines.append(dialogue)

    out_ass_path.write_text("".join(lines), encoding="utf-8")
    logger.info("Generated kinetic ASS subtitle track (%d words -> %s)", len(words), out_ass_path.name)
    return out_ass_path


def _read_stereo_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
        channels = wf.getnchannels()
        if channels == 2:
            return arr.reshape(-1, 2)
        return np.stack([arr, arr], axis=1)


def _build_sfx_stem(
    timed_beats: List[Dict[str, Any]],
    sfx_assets: Dict[str, Path],
    total_duration: float,
    out_wav: Path,
) -> Path:
    """Place every beat transition SFX at sample-exact millisecond timestamps on a clean stereo stem."""
    total_samples = int(math.ceil((total_duration + 0.4) * SAMPLE_RATE))
    stem = np.zeros((total_samples, 2), dtype=np.float32)

    loaded_cache: Dict[str, np.ndarray] = {}
    sfx_gains = {
        "sub_boom": 0.58,
        "whoosh": 0.34,
        "tick": 0.24,
        "sonar": 0.30,
        "glitch": 0.32,
        "riser": 0.34,
    }

    # Always fire sub_boom + subtle whoosh right at 0.00s for the 0-2s Shock Hook!
    events: List[Tuple[float, str, float]] = [(0.0, "sub_boom", 0.65), (0.04, "whoosh", 0.30)]
    for idx, beat in enumerate(timed_beats):
        sfx_name = beat.get("sfx", "none")
        if idx == 0 or sfx_name == "none" or sfx_name not in sfx_assets:
            continue
        ts = max(0.0, float(beat["start"]) - (0.08 if sfx_name == "whoosh" else 0.0))
        events.append((ts, sfx_name, sfx_gains.get(sfx_name, 0.30)))

    for ts, name, gain in events:
        if name not in loaded_cache:
            loaded_cache[name] = _read_stereo_wav(sfx_assets[name])
        clip = loaded_cache[name] * gain
        start_idx = int(ts * SAMPLE_RATE)
        end_idx = min(total_samples, start_idx + len(clip))
        if end_idx > start_idx:
            stem[start_idx:end_idx] += clip[: end_idx - start_idx]

    # Soft clip safety
    peak = float(np.max(np.abs(stem)))
    if peak > 0.92:
        stem *= 0.92 / peak

    pcm = np.clip(stem * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return out_wav


def _mix_master_cinema_audio(
    narration_wav: Path,
    tension_bed_wav: Path,
    sfx_stem_wav: Path,
    out_audio_wav: Path,
    total_duration: float,
    target_lufs: float = -14.0,
) -> Path:
    """Mix voice + auto-ducked tension bed (`sidechaincompress`) + SFX and master to -14 LUFS."""
    ffmpeg = get_ffmpeg_bin()
    # Auto-ducking: narration triggers sidechaincompress on tension bed so music dips when speaking
    filter_complex = (
        "[0:a]asplit=2[voice_main][voice_sc];"
        "[1:a]volume=0.26[bed_lvl];"
        "[bed_lvl][voice_sc]sidechaincompress=threshold=0.018:ratio=7.5:attack=15:release=320:makeup=1[bed_ducked];"
        "[2:a]volume=0.85[sfx_lvl];"
        "[voice_main][bed_ducked][sfx_lvl]amix=inputs=3:duration=first:normalize=0,"
        f"loudnorm=I={target_lufs:.1f}:TP=-1.5:LRA=8,"
        f"atrim=0:{total_duration:.3f},asetpts=PTS-STARTPTS[aout]"
    )
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(narration_wav),
        "-i",
        str(tension_bed_wav),
        "-i",
        str(sfx_stem_wav),
        "-filter_complex",
        filter_complex,
        "-map",
        "[aout]",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        str(out_audio_wav),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info("Mixed auto-ducked 3-stem cinema audio mastered to %.1f LUFS", target_lufs)
    return out_audio_wav


def compose_cinematic_video(
    script: Dict[str, Any],
    voice_data: Dict[str, Any],
    output_mp4: Path,
    work_dir: Path,
    target_lufs: float = -14.0,
) -> Dict[str, Any]:
    """Compose the full 1080p 60fps Broadcast-Grade cinematic MP4 with HUD, captions, SFX & auto-ducking."""
    fmt = script["format"]
    size = (1080, 1920) if fmt == "shorts" else (1920, 1080)
    w, h = size
    fps = 60
    total_dur = float(voice_data["duration"])
    timed_beats = voice_data["timed_beats"]
    words = voice_data["words"]

    logger.info(
        "Composing %s cinematic video (%dx%d @ %dfps, %.2fs, %d beats)...",
        fmt,
        w,
        h,
        fps,
        total_dur,
        len(timed_beats),
    )

    # 1. Generate royalty-free SFX & duration-matched tension underscore
    sfx_assets = generate_audio_pack(work_dir, total_dur)
    sfx_stem = _build_sfx_stem(
        timed_beats, sfx_assets, total_dur, work_dir / "audio_assets" / "sfx_stem.wav"
    )
    master_wav = _mix_master_cinema_audio(
        Path(voice_data["clean_wav"]),
        sfx_assets["tension_bed"],
        sfx_stem,
        work_dir / "audio_assets" / "master_mix.wav",
        total_dur,
        target_lufs=target_lufs,
    )

    # 2. Generate Whisper-synced kinetic ASS subtitle file
    ass_path = build_kinetic_ass_subtitles(words, work_dir / "kinetic_captions.ass", size)

    # 3. Prepare visual assets per beat (real graded photos + animated Vox data plates)
    fetcher = MediaFetcher(work_dir / "media_cache")
    beat_visuals: List[Dict[str, Any]] = []
    for idx, beat in enumerate(timed_beats):
        if beat["visual_type"] == "photo_grade":
            photo_path = fetcher.fetch_photo_plate(beat["visual_query"], size, variant_index=idx)
            # Load via Pillow for full cross-platform Unicode path safety
            pil_photo = Image.open(photo_path).convert("RGB")
            raw_bgr = cv2.cvtColor(np.asarray(pil_photo), cv2.COLOR_RGB2BGR)
            graded = _apply_cinematic_grade(raw_bgr)
            beat_visuals.append({"kind": "photo", "image": graded})
        else:
            # Pre-render 14 smooth entrance animation frames for buttery Vox motion graphics
            anim_frames: List[np.ndarray] = []
            steps = 14
            for s in range(steps):
                anim_t = s / max(steps - 1, 1)
                pil_plate = render_data_plate(
                    beat.get("plate_mode", "metric_hero"),
                    beat.get("plate_data", {}),
                    size,
                    anim_t=anim_t,
                )
                bgr_plate = cv2.cvtColor(np.asarray(pil_plate), cv2.COLOR_RGB2BGR)
                anim_frames.append(bgr_plate)
            beat_visuals.append({"kind": "plate", "frames": anim_frames})

    # 4. Stream 60fps frames directly into FFmpeg (zero temp uncompressed disk bloat!)
    raw_video_mp4 = work_dir / "visual_track_60fps.mp4"
    ffmpeg = get_ffmpeg_bin()
    pipe_cmd = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "15",
        "-pix_fmt",
        "yuv420p",
        str(raw_video_mp4),
    ]

    proc = subprocess.Popen(
        pipe_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    total_frames = max(1, int(round(total_dur * fps)))
    hook_text = script["hook_stat_text"]
    hook_sub = script.get("hook_subtext", "VELUM ARCHIVE TELEMETRY")
    hook_window = 2.0

    # Pre-assign frame ranges to beats
    beat_cursor = 0
    cached_hud_blend: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None
    prev_beat_last_frame: Optional[np.ndarray] = None
    transition_frames = 5  # Crisp 83ms dark cinema cut crossfade

    assert proc.stdin is not None
    try:
        for frame_idx in range(total_frames):
            t_sec = frame_idx / fps
            global_prog = t_sec / max(total_dur, 0.001)

            # Advance beat cursor
            while (
                beat_cursor + 1 < len(timed_beats)
                and t_sec >= float(timed_beats[beat_cursor]["end"])
            ):
                beat_cursor += 1

            beat = timed_beats[beat_cursor]
            b_start = float(beat["start"])
            b_dur = max(0.1, float(beat["end"]) - b_start)
            local_t = max(0.0, min(1.0, (t_sec - b_start) / b_dur))
            local_frame = int(round((t_sec - b_start) * fps))

            vis = beat_visuals[beat_cursor]
            if vis["kind"] == "photo":
                frame_bgr = _ken_burns_frame(
                    vis["image"], w, h, local_t, beat.get("camera_motion", "zoom_in")
                )
            else:
                plates = vis["frames"]
                # Animate entrance over first 0.72s, then subtle Ken Burns breathing drift
                enter_t = min(1.0, (t_sec - b_start) / 0.72)
                p_idx = min(len(plates) - 1, int(round(enter_t * (len(plates) - 1))))
                base_plate = plates[p_idx]
                # Subtle 1.00 -> 1.035 continuous camera breathing so plate NEVER freezes
                scale = 1.0 + 0.035 * local_t
                tx = (w * (1.0 - scale)) * 0.5
                ty = (h * (1.0 - scale)) * 0.5
                mat = np.array([[scale, 0.0, tx], [0.0, scale, ty]], dtype=np.float32)
                frame_bgr = cv2.warpAffine(
                    base_plate, mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
                )

            # Crisp cinema beat-transition crossfade
            if beat_cursor > 0 and local_frame < transition_frames and prev_beat_last_frame is not None:
                blend_a = (local_frame + 1) / (transition_frames + 1)
                frame_bgr = cv2.addWeighted(
                    frame_bgr, blend_a, prev_beat_last_frame, 1.0 - blend_a, 0.0
                )

            # Capture last frame before beat switch for smooth next transition
            if beat_cursor + 1 < len(timed_beats):
                next_start = float(timed_beats[beat_cursor + 1]["start"])
                if abs((t_sec + 1.0 / fps) - next_start) < (1.2 / fps):
                    prev_beat_last_frame = frame_bgr.copy()

            # Refresh live HUD at 15fps (every 4 frames) + always on frame 0 and beat switches
            if frame_idx % 4 == 0 or local_frame == 0 or cached_hud_blend is None:
                in_hook = t_sec <= hook_window
                hud_pil = render_hud_overlay(
                    size=size,
                    global_progress=global_prog,
                    hud_tag=beat["hud_tag"],
                    hud_metric=beat["hud_metric"],
                    hud_delta=beat["hud_delta"],
                    time_sec=t_sec,
                    shock_hook_text=hook_text if in_hook else None,
                    shock_hook_sub=hook_sub if in_hook else None,
                    shock_progress=(t_sec / hook_window) if in_hook else -1.0,
                )
                cached_hud_blend = _prepare_hud_blend_cache(np.asarray(hud_pil, dtype=np.uint8))

            composited = _apply_hud_blend_fast(frame_bgr, *cached_hud_blend)
            proc.stdin.write(composited.tobytes())
    finally:
        proc.stdin.close()

    stderr_out = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"FFmpeg rawvideo encode failed (code={ret}): {stderr_out[-600:]}")

    # 5. Burn kinetic ASS subtitles + mux mastered 3-stem cinema audio into final deliverable MP4
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    final_cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(raw_video_mp4.resolve()),
        "-i",
        str(master_wav.resolve()),
        "-vf",
        f"ass={ass_path.name}",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_mp4.resolve()),
    ]
    res = subprocess.run(
        final_cmd,
        cwd=str(work_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg final mux/ASS burn failed: {res.stderr[-700:]}")

    logger.info("Final cinematic MP4 rendered: %s (%.2f MB)", output_mp4.name, output_mp4.stat().st_size / 1e6)
    return {
        "video_path": str(output_mp4),
        "width": w,
        "height": h,
        "fps": fps,
        "duration": total_dur,
        "beat_count": len(timed_beats),
        "ass_path": str(ass_path),
    }
