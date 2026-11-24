"""Broadcast-Grade 4K Shorts / 1080p Long-Form 60fps Cinematic Video Compositor (FFmpeg + OpenCV + LibASS).

Features:
- Fast internal 60fps subpixel Ken Burns zoom/pan at 1080x1920 / 1920x1080 (zero zoompan integer jitter)
- True 4K Vertical (2160x3840 @ 60fps) Lanczos + Unsharp final master for Shorts to force YouTube VP9/AV1
- Parallel beat media prefetching with alternating graded footage & animated Netflix/Vox data plates (<=2.5s cuts)
- 0-2.1s high-contrast Shock Hook explosion + sub-bass/whoosh audio punch
- Live Telemetry HUD overlay (progress rail, live metrics, open-loop retention badge, watermark)
- Dark Netflix/Vox cinematic color grading (teal-obsidian shadow LUT + vignette)
- Word-by-word kinetic scaling ASS captions synchronized to Whisper timestamps
- 3-stem cinema audio: cleaned narration + auto-ducked tension bed (`sidechaincompress`)
  + sample-accurate beat-synced SFX track, mastered via FFmpeg `loudnorm` (-14 LUFS)
"""

from __future__ import annotations

import gc
import math
import re
import subprocess
import wave
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from core.config import get_ffmpeg_bin, get_logger, load_brand_config, resolve_font
from engine.hud_renderer import render_data_plate, render_hud_overlay
from engine.media_fetcher import MediaFetcher
from engine.schematic_engine import render_v6_schematic_frame
from engine.sfx_music_engine import SAMPLE_RATE, generate_audio_pack

logger = get_logger("video_composer")


def _build_grade_luts() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Precompute vibrant cinema S-curve, adaptive shadow-lift LUT, and split-tone LUTs."""
    x = np.arange(256, dtype=np.float32) / 255.0
    exp_x = np.clip(x * 0.96 + 0.015, 0.0, 1.0)
    scurve = np.clip(exp_x * exp_x * (3.0 - 2.0 * exp_x) * 0.45 + exp_x * 0.55, 0.0, 1.0)
    curve_lut = np.clip(np.rint(scurve * 255.0), 0, 255).astype(np.uint8)

    lifted = np.clip((x**0.82) * 1.06 + 0.02, 0.0, 1.0)
    lifted_scurve = np.clip(lifted * lifted * (3.0 - 2.0 * lifted) * 0.35 + lifted * 0.65, 0.0, 1.0)
    dark_lift_lut = np.clip(np.rint(lifted_scurve * 255.0), 0, 255).astype(np.uint8)

    luma = np.arange(256, dtype=np.float32) / 255.0
    shadow_w = np.clip(1.0 - luma * 1.7, 0.0, 1.0)
    high_w = np.clip((luma - 0.48) * 1.8, 0.0, 1.0)
    split_lut = np.stack(
        [
            np.rint((shadow_w * 0.042 - high_w * 0.018) * 255.0),  # B
            np.rint((shadow_w * 0.016 + high_w * 0.012) * 255.0),  # G
            np.rint((-shadow_w * 0.014 + high_w * 0.040) * 255.0),  # R
        ],
        axis=1,
    ).astype(np.int16)
    return curve_lut, dark_lift_lut, split_lut


_GRADE_CURVE_LUT, _DARK_LIFT_LUT, _SPLIT_TONE_LUT = _build_grade_luts()


@lru_cache(maxsize=8)
def _get_vignette_mask_u16(h: int, w: int) -> np.ndarray:
    """Precompute and cache subtle Q8 radial vignette mask (keeps edges bright and crisp)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx / max(w - 1, 1) - 0.5) * 2.0
    ny = (yy / max(h - 1, 1) - 0.5) * 2.0
    dist2 = nx * nx + ny * ny
    vig = np.clip(1.0 - 0.16 * (dist2**1.25), 0.78, 1.0)[:, :, None]
    return np.rint(vig * 256.0).astype(np.uint16)


def _apply_cinematic_grade(bgr: np.ndarray) -> np.ndarray:
    """Apply crisp, bright Netflix/Vox teal-amber cinema grade with adaptive dark-scene lift."""
    sample_mean = float(bgr[::16, ::16].mean())
    lut = _DARK_LIFT_LUT if sample_mean < 66.0 else _GRADE_CURVE_LUT
    base = cv2.LUT(bgr, lut)
    gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    toned = np.clip(base.astype(np.int16) + _SPLIT_TONE_LUT[gray], 0, 255).astype(np.uint16)
    h, w = bgr.shape[:2]
    return ((toned * _get_vignette_mask_u16(h, w)) >> 8).astype(np.uint8)


def _extract_hero_bg_pil(
    spec: Dict[str, Any], fetcher: MediaFetcher, size: Tuple[int, int]
) -> Optional[Image.Image]:
    """Load a vibrant real HD background frame behind Frame-0 Thumbnail Cover / Closing Debate CTA."""
    w, h = size
    clip_path = spec.get("hero_clip_path")
    if clip_path is not None and Path(clip_path).exists():
        cap = cv2.VideoCapture(str(clip_path))
        try:
            ok, f_bgr = cap.read()
            if ok and f_bgr is not None:
                if f_bgr.shape[1] != w or f_bgr.shape[0] != h:
                    f_bgr = cv2.resize(f_bgr, (w, h), interpolation=cv2.INTER_LINEAR)
                graded = _apply_cinematic_grade(f_bgr)
                return Image.fromarray(cv2.cvtColor(graded, cv2.COLOR_BGR2RGB))
        finally:
            cap.release()
    photo_path = spec.get("hero_photo_path")
    if photo_path is None and spec.get("query"):
        photo_path = fetcher.fetch_photo_plate(spec["query"], size, variant_index=int(spec.get("idx", 0)))
    if photo_path is not None and Path(photo_path).exists():
        pil_img = Image.open(photo_path).convert("RGB")
        if pil_img.size != (w, h):
            pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
        graded = _apply_cinematic_grade(cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR))
        return Image.fromarray(cv2.cvtColor(graded, cv2.COLOR_BGR2RGB))
    return None


def _load_beat_visual(
    spec: Dict[str, Any],
    fetcher: MediaFetcher,
    size: Tuple[int, int],
) -> Dict[str, Any]:
    """Materialize a single beat's graded frames on demand so peak RAM stays under ~450 MB."""
    w, h = size
    if spec["kind"] == "v6_schematic":
        sch_frames: List[np.ndarray] = []
        steps = 40
        for s in range(steps):
            phase_t = s / max(steps - 1, 1)
            anim_t = min(1.0, phase_t * 2.35)
            pil_sch = render_v6_schematic_frame(
                schematic_mode=spec.get("schematic_mode", "step_sequence_blueprint"),
                schematic_data=spec.get("schematic_data", {}),
                size=size,
                anim_t=anim_t,
                phase_t=phase_t,
                chapter_num=int(spec.get("chapter_num", 1)),
                total_chapters=int(spec.get("total_chapters", 6)),
                chapter_tag=str(spec.get("chapter_tag", "MECHANISM")),
                headline_line1=str(spec.get("headline_line1", "HIDDEN SCALE")),
                headline_line2=str(spec.get("headline_line2", "EXPOSED")),
                accent_word=str(spec.get("accent_word", "")),
                episode_num=int(spec.get("episode_num", 9)),
                source_credit=str(spec.get("source_credit", "VELUM ARCHIVE")),
            )
            sch_frames.append(cv2.cvtColor(np.asarray(pil_sch), cv2.COLOR_RGB2BGR))
        return {"kind": "v6_schematic", "frames": sch_frames}

    if spec["kind"] == "photo_grade":
        clip_path = spec.get("clip_path")
        max_frames = int(spec.get("max_frames", 72))
        clip_frames: List[np.ndarray] = []
        if clip_path is not None:
            cap = cv2.VideoCapture(str(clip_path))
            try:
                while len(clip_frames) < max_frames:
                    ok, f_bgr = cap.read()
                    if not ok or f_bgr is None:
                        break
                    if f_bgr.shape[1] != w or f_bgr.shape[0] != h:
                        f_bgr = cv2.resize(f_bgr, (w, h), interpolation=cv2.INTER_LINEAR)
                    clip_frames.append(_apply_cinematic_grade(f_bgr))
            finally:
                cap.release()
        if len(clip_frames) >= 12:
            return {"kind": "video", "frames": clip_frames}
        photo_path = spec.get("photo_path") or fetcher.fetch_photo_plate(
            spec["query"], size, variant_index=int(spec["idx"])
        )
        pil_photo = Image.open(photo_path).convert("RGB")
        raw_bgr = cv2.cvtColor(np.asarray(pil_photo), cv2.COLOR_RGB2BGR)
        return {"kind": "photo", "image": _apply_cinematic_grade(raw_bgr)}

    anim_frames: List[np.ndarray] = []
    steps = 28
    plate_mode = spec.get("plate_mode", "metric_hero")
    plate_data = spec.get("plate_data", {})
    hero_bg = (
        _extract_hero_bg_pil(spec, fetcher, size)
        if plate_mode in ("split_vs_clash", "debate_cta_plate", "dual_fact_spotlight")
        else None
    )
    for s in range(steps):
        phase_t = s / max(steps - 1, 1)
        anim_t = min(1.0, phase_t * 1.42)
        pil_plate = render_data_plate(
            plate_mode,
            plate_data,
            size,
            anim_t=anim_t,
            phase_t=phase_t,
            bg_image=hero_bg,
        )
        anim_frames.append(cv2.cvtColor(np.asarray(pil_plate), cv2.COLOR_RGB2BGR))
    return {"kind": "plate", "frames": anim_frames}


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
        scale = min_scale * (1.03 + 0.13 * smooth_t)
        dx_frac, dy_frac = 0.0, 0.0
    elif motion == "zoom_out":
        scale = min_scale * (1.16 - 0.12 * smooth_t)
        dx_frac, dy_frac = 0.0, 0.0
    elif motion == "pan_right":
        scale = min_scale * 1.14
        dx_frac = -0.05 + 0.10 * smooth_t
        dy_frac = 0.0
    elif motion == "pan_left":
        scale = min_scale * 1.14
        dx_frac = 0.05 - 0.10 * smooth_t
        dy_frac = 0.0
    else:  # drift_up
        scale = min_scale * (1.06 + 0.08 * smooth_t)
        dx_frac = 0.0
        dy_frac = 0.045 - 0.09 * smooth_t

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
    editorial_v6: bool = False,
) -> Path:
    """Generate Whisper-synced captions (V6 clean editorial style or kinetic Shorts pop)."""
    w, h = size
    is_vertical = h > w

    # Resolve crisp bold font family name for libass across Windows and Ubuntu Linux
    font_path = resolve_font("body" if editorial_v6 else "headline").lower()
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

    if editorial_v6 and is_vertical:
        font_size = 56
        margin_v = 435
        margin_lr = 74
        outline_w = 2
        shadow_w = 2
        spacing = 0.6
    else:
        font_size = 88 if is_vertical else 68
        margin_v = 470 if is_vertical else 78
        margin_lr = 58 if is_vertical else 120
        outline_w = 8
        shadow_w = 4
        spacing = 1.2

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kinetic,{font_name},{font_size},&H00FAF7F5,&H000B9EF5,&H00070C14,&H88070C14,-1,0,0,0,100,100,{spacing},0,1,{outline_w},{shadow_w},2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Fuse split Whisper numeric/currency tokens ("$1" + ".2" -> "$1.2", "99" + "%" -> "99%")
    merged_words: List[Dict[str, Any]] = []
    for raw_w in words:
        tok = str(raw_w.get("word", "")).strip()
        if not tok:
            continue
        if merged_words and (
            tok.startswith((".", ",", "%", "'", "’"))
            or (re.match(r"^\d", tok) and merged_words[-1]["word"].endswith(("$", ".", ",")))
            or tok.lower() in ("ms", "km", "°c", "°f")
        ):
            merged_words[-1]["word"] = merged_words[-1]["word"] + tok
            merged_words[-1]["end"] = max(float(merged_words[-1]["end"]), float(raw_w["end"]))
        else:
            merged_words.append(dict(raw_w, word=tok))

    # Group words cleanly (V6 editorial: 4-5 natural sentence words; kinetic mode: 2-word punch)
    if editorial_v6 and is_vertical:
        max_words_grp = 5
        max_chars_grp = 30
    else:
        max_words_grp = 2 if is_vertical else 3
        max_chars_grp = 15 if is_vertical else 22
    groups: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    for word_item in merged_words:
        token = word_item["word"].strip()
        if not token:
            continue
        cur.append(word_item)
        cur_chars = sum(len(x["word"]) for x in cur) + max(0, len(cur) - 1)
        ends_sentence = token.endswith((".", "!", "?", "—", ":"))
        if len(cur) >= max_words_grp or cur_chars >= max_chars_grp or ends_sentence:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    lines: List[str] = [header]
    for grp in groups:
        for active_idx, active_w in enumerate(grp):
            start = float(active_w["start"])
            if active_idx + 1 < len(grp):
                end = max(start + 0.07, float(grp[active_idx + 1]["start"]))
            else:
                end = max(start + 0.11, float(active_w["end"]))

            parts: List[str] = []
            for j, w_obj in enumerate(grp):
                raw_word = w_obj["word"] if editorial_v6 else w_obj["word"].upper()
                raw_txt = _escape_ass_text(raw_word)
                is_numeric = bool(re.search(r"\d|\$|%", raw_txt))
                if j == active_idx:
                    if editorial_v6:
                        hi_col = "&H00EED322&" if is_numeric else "&H000B9EF5&"
                        parts.append(f"{{\\rKinetic\\fs{font_size}\\c{hi_col}}}{raw_txt}{{\\rKinetic}}")
                    else:
                        hi_col = "&H00FFE500&" if is_numeric else "&H0000B8FF&"
                        parts.append(
                            f"{{\\rKinetic\\fs{font_size}\\c{hi_col}\\fscx122\\fscy122\\t(0,85,\\fscx100\\fscy100)}}{raw_txt}{{\\rKinetic}}"
                        )
                else:
                    parts.append(
                        f"{{\\rKinetic\\fs{font_size}\\c&H00FAF7F5&\\alpha&H12&}}{raw_txt}{{\\rKinetic}}"
                    )

            dialogue = (
                f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},"
                f"Kinetic,,0,0,0,,{' '.join(parts)}\n"
            )
            lines.append(dialogue)

    out_ass_path.write_text("".join(lines), encoding="utf-8")
    logger.info("Generated %s ASS subtitle track (%d words -> %s)", "editorial V6" if editorial_v6 else "kinetic", len(words), out_ass_path.name)
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
    twist_drop_sec: Optional[float] = None,
) -> Path:
    """Mix voice + auto-ducked tension bed (+ V7 0.22s Twist Silence Shock) + SFX at -14 LUFS."""
    ffmpeg = get_ffmpeg_bin()
    # V7 Dramatic Silence Shock: dip music bed to near-zero for 220ms right before THE TWIST drops!
    bed_mute_filter = ""
    if twist_drop_sec is not None and 4.0 < twist_drop_sec < (total_duration - 2.0):
        t0 = max(0.0, twist_drop_sec - 0.22)
        t1 = twist_drop_sec
        bed_mute_filter = f",volume=enable='between(t,{t0:.3f},{t1:.3f})':volume=0.03"

    # Auto-ducking: narration triggers sidechaincompress on tension bed so music dips when speaking
    filter_complex = (
        "[0:a]asplit=2[voice_main][voice_sc];"
        "[1:a]volume=0.26[bed_lvl];"
        f"[bed_lvl][voice_sc]sidechaincompress=threshold=0.018:ratio=7.5:attack=15:release=320:makeup=1{bed_mute_filter}[bed_ducked];"
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
    """Compose the 4K Shorts (2160x3840) / 1080p Long-form 60fps cinematic MP4 with HUD, captions & audio."""
    fmt = script["format"]
    size = (1080, 1920) if fmt == "shorts" else (1920, 1080)
    w, h = size
    out_w, out_h = (2160, 3840) if fmt == "shorts" else (w, h)
    fps = 60
    total_dur = float(voice_data["duration"])
    timed_beats = voice_data["timed_beats"]
    words = voice_data["words"]

    logger.info(
        "Composing %s cinematic video (render %dx%d -> master %dx%d @ %dfps, %.2fs, %d beats)...",
        fmt,
        w,
        h,
        out_w,
        out_h,
        fps,
        total_dur,
        len(timed_beats),
    )

    # 1. Generate royalty-free SFX & duration-matched tension underscore (+ V7 Twist Silence Shock)
    sfx_assets = generate_audio_pack(work_dir, total_dur)
    twist_drop_sec: Optional[float] = None
    if len(timed_beats) >= 5:
        twist_drop_sec = float(timed_beats[-2].get("start", 0.0))
        timed_beats[-2]["sfx"] = "sub_boom"
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
        twist_drop_sec=twist_drop_sec,
    )

    is_v6 = bool(script.get("v6_schematic_mode"))
    ep_num = int(script.get("episode_num", 9))

    # 2. Generate Whisper-synced editorial V6 or kinetic ASS subtitle file
    ass_path = build_kinetic_ass_subtitles(
        words, work_dir / "kinetic_captions.ass", size, editorial_v6=is_v6
    )

    # 3. Prefetch & resolve lightweight beat asset descriptors (frames load 1 beat at a time to prevent OOM)
    fetcher = MediaFetcher(work_dir / "media_cache")
    if not is_v6 and hasattr(fetcher, "prefetch_beats"):
        prefetch_summary = fetcher.prefetch_beats(timed_beats, size)
        logger.info("Parallel media prefetch complete: %s", prefetch_summary)
    beat_specs: List[Dict[str, Any]] = []
    for idx, beat in enumerate(timed_beats):
        beat_dur = max(0.1, float(beat.get("end", 0.0)) - float(beat.get("start", 0.0)))
        if beat_dur <= 0.11:
            beat_dur = float(beat.get("duration", 2.2))
        if beat.get("visual_type") == "v6_schematic":
            beat_specs.append(
                {
                    "kind": "v6_schematic",
                    "idx": idx,
                    "schematic_mode": beat.get("schematic_mode", "step_sequence_blueprint"),
                    "schematic_data": beat.get("schematic_data", {}),
                    "chapter_num": int(beat.get("chapter_num", idx + 1)),
                    "total_chapters": int(beat.get("total_chapters", len(timed_beats))),
                    "chapter_tag": str(beat.get("chapter_tag", "MECHANISM")),
                    "headline_line1": str(beat.get("headline_line1", "HIDDEN SCALE")),
                    "headline_line2": str(beat.get("headline_line2", "EXPOSED")),
                    "accent_word": str(beat.get("accent_word", "")),
                    "episode_num": ep_num,
                    "source_credit": str(beat.get("source_credit", "VELUM ARCHIVE")),
                }
            )
            continue
        if beat["visual_type"] == "photo_grade":
            clip_path = fetcher.fetch_motion_clip(
                beat["visual_query"],
                size,
                duration_sec=beat_dur,
                variant_index=idx,
            )
            photo_path = None
            if clip_path is None:
                photo_path = fetcher.fetch_photo_plate(beat["visual_query"], size, variant_index=idx)
            beat_specs.append(
                {
                    "kind": "photo_grade",
                    "idx": idx,
                    "query": beat["visual_query"],
                    "clip_path": clip_path,
                    "photo_path": photo_path,
                    "max_frames": max(18, min(110, int(math.ceil(beat_dur * 30.0)) + 6)),
                }
            )
        else:
            p_mode = beat.get("plate_mode", "metric_hero")
            hero_clip_path = None
            hero_photo_path = None
            if p_mode in ("split_vs_clash", "debate_cta_plate", "dual_fact_spotlight"):
                hero_clip_path = fetcher.fetch_motion_clip(
                    beat["visual_query"],
                    size,
                    duration_sec=beat_dur,
                    variant_index=idx,
                )
                if hero_clip_path is None:
                    hero_photo_path = fetcher.fetch_photo_plate(
                        beat["visual_query"], size, variant_index=idx
                    )
            beat_specs.append(
                {
                    "kind": "plate",
                    "idx": idx,
                    "query": beat["visual_query"],
                    "plate_mode": p_mode,
                    "plate_data": beat.get("plate_data", {}),
                    "hero_clip_path": hero_clip_path,
                    "hero_photo_path": hero_photo_path,
                }
            )

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
        "14",
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
    hook_window = 1.85

    beat_cursor = 0
    active_beat_idx = -1
    active_vis: Optional[Dict[str, Any]] = None
    cached_hud_blend: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None
    prev_beat_last_frame: Optional[np.ndarray] = None
    transition_frames = 4  # Snappy 66ms whip-zoom impact cut

    assert proc.stdin is not None
    try:
        for frame_idx in range(total_frames):
            t_sec = frame_idx / fps
            global_prog = t_sec / max(total_dur, 0.001)

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

            if beat_cursor != active_beat_idx or active_vis is None:
                active_vis = None
                active_vis = _load_beat_visual(beat_specs[beat_cursor], fetcher, size)
                active_beat_idx = beat_cursor

            vis = active_vis
            if vis["kind"] == "v6_schematic":
                s_frames = vis["frames"]
                s_pos = local_t * (len(s_frames) - 1)
                frame_bgr = s_frames[min(len(s_frames) - 1, int(round(s_pos)))]
                # Silky 4-frame editorial crossfade between schematic chapters (steady top chrome!)
                if beat_cursor > 0 and local_frame < transition_frames and prev_beat_last_frame is not None:
                    alpha_cf = (local_frame + 1) / float(transition_frames + 1)
                    frame_bgr = cv2.addWeighted(frame_bgr, alpha_cf, prev_beat_last_frame, 1.0 - alpha_cf, 0.0)
                if beat_cursor + 1 < len(timed_beats):
                    next_start = float(timed_beats[beat_cursor + 1]["start"])
                    if abs((t_sec + 1.0 / fps) - next_start) < (1.2 / fps):
                        prev_beat_last_frame = frame_bgr.copy()
                proc.stdin.write(frame_bgr.tobytes())
                continue
            elif vis["kind"] == "video":
                v_frames = vis["frames"]
                vf_pos = local_t * (len(v_frames) - 1)
                vf_idx = min(len(v_frames) - 1, int(vf_pos))
                base_v = v_frames[vf_idx]
                # Subtle dynamic cinema push-in on top of real moving footage
                v_scale = 1.01 + 0.045 * local_t
                v_tx = (w * (1.0 - v_scale)) * 0.5
                v_ty = (h * (1.0 - v_scale)) * 0.5
                v_mat = np.array([[v_scale, 0.0, v_tx], [0.0, v_scale, v_ty]], dtype=np.float32)
                frame_bgr = cv2.warpAffine(
                    base_v, v_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
                )
            elif vis["kind"] == "photo":
                frame_bgr = _ken_burns_frame(
                    vis["image"], w, h, local_t, beat.get("camera_motion", "zoom_in")
                )
            else:
                plates = vis["frames"]
                # Crisp nearest keyframe lookup prevents double-exposed ghosting on rolling numeric counters
                f_pos = local_t * (len(plates) - 1)
                idx_nearest = min(len(plates) - 1, int(round(f_pos)))
                base_plate = plates[idx_nearest]
                # Smooth 1.00 -> 1.04 continuous camera push so every pixel breathes at 60fps
                scale = 1.0 + 0.04 * local_t
                tx = (w * (1.0 - scale)) * 0.5
                ty = (h * (1.0 - scale)) * 0.5
                mat = np.array([[scale, 0.0, tx], [0.0, scale, ty]], dtype=np.float32)
                frame_bgr = cv2.warpAffine(
                    base_plate, mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
                )

            # Snappy whip-zoom impact cut + subtle cinema flash pop on beat transitions
            if beat_cursor > 0 and local_frame < transition_frames:
                punch_decay = 1.0 - (local_frame / float(transition_frames))
                p_scale = 1.0 + 0.055 * punch_decay
                p_tx = (w * (1.0 - p_scale)) * 0.5
                p_ty = (h * (1.0 - p_scale)) * 0.5
                p_mat = np.array([[p_scale, 0.0, p_tx], [0.0, p_scale, p_ty]], dtype=np.float32)
                frame_bgr = cv2.warpAffine(
                    frame_bgr, p_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
                )
                if prev_beat_last_frame is not None and local_frame < 2:
                    blend_a = 0.62 + 0.25 * local_frame
                    frame_bgr = cv2.addWeighted(
                        frame_bgr, blend_a, prev_beat_last_frame, 1.0 - blend_a, 14.0 * punch_decay
                    )

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
                    total_duration=total_dur,
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

    # Release all decoded beat frames, HUD masks & transition buffers before spawning 4K libx264
    active_vis = None
    vis = None
    prev_beat_last_frame = None
    cached_hud_blend = None
    beat_specs.clear()
    gc.collect()

    # 5. Burn kinetic ASS subtitles (+ true 4K Lanczos upscale for Shorts to force YouTube VP9/AV1)
    #    and mux mastered 3-stem cinema audio into high-bitrate MP4
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "shorts":
        vf_filter = (
            f"ass={ass_path.name},"
            "scale=2160:3840:flags=lanczos,"
            "unsharp=5:5:0.70:5:5:0.0,"
            "eq=contrast=1.05:saturation=1.12"
        )
        crf_val = "18"
        bitrate_guard = ["-maxrate", "45M", "-bufsize", "90M", "-threads", "4"]
    else:
        vf_filter = f"ass={ass_path.name},unsharp=3:3:0.45:3:3:0.0,eq=contrast=1.04:saturation=1.08"
        crf_val = "17"
        bitrate_guard = ["-maxrate", "25M", "-bufsize", "50M", "-threads", "4"]

    final_cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(raw_video_mp4.resolve()),
        "-i",
        str(master_wav.resolve()),
        "-vf",
        vf_filter,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        crf_val,
        *bitrate_guard,
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

    logger.info(
        "Final cinematic MP4 rendered (%dx%d @ %dfps): %s (%.2f MB)",
        out_w,
        out_h,
        fps,
        output_mp4.name,
        output_mp4.stat().st_size / 1e6,
    )
    return {
        "video_path": str(output_mp4),
        "width": out_w,
        "height": out_h,
        "fps": fps,
        "duration": total_dur,
        "beat_count": len(timed_beats),
        "ass_path": str(ass_path),
    }
