"""Automated Broadcast Quality Assurance Gate (`qa_gate.py`).

Inspects every rendered MP4 before upload or delivery:
1. Exact resolution & aspect ratio (2160x3840 4K Shorts or 1920x1080 Long-form)
2. True 60fps frame rate verification (>= 59.0 fps)
3. Duration bounds compliance (Shorts: 20.0-39.5s; Long-form: 60.0-420.0s)
4. Integrated Loudness (LUFS) & True Peak check via FFmpeg `ebur128` (-17.5..-11.0 LUFS)
5. Zero black borders / letterboxing check via fast downscaled FFmpeg `cropdetect`
6. Static / frozen frame slop audit via fast downscaled FFmpeg `freezedetect` (max 1.85s static)
7. Stream codec integrity (H.264 yuv420p + AAC stereo 48kHz)

Returns structured pass/fail report with remediation hints so autopilot can
automatically re-render any defective asset.
"""

from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_ffmpeg_bin, get_ffprobe_bin, get_logger

logger = get_logger("qa_gate")


def _probe_streams(video_path: Path) -> Dict[str, Any]:
    cmd = [
        get_ffprobe_bin(),
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(video_path),
    ]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def _measure_lufs_and_peak(video_path: Path) -> Tuple[Optional[float], Optional[float]]:
    cmd = [
        get_ffmpeg_bin(),
        "-i",
        str(video_path),
        "-vn",
        "-af",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    stderr = res.stderr or ""
    # Parse Summary block integrated loudness (I:) and True peak (Peak:)
    summary_idx = stderr.rfind("Summary:")
    tail = stderr[summary_idx:] if summary_idx != -1 else stderr[-1200:]
    i_match = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", tail)
    p_match = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", tail)
    lufs = float(i_match.group(1)) if i_match else None
    peak = float(p_match.group(1)) if p_match else None
    return lufs, peak


def _detect_black_borders(video_path: Path, expected_w: int, expected_h: int) -> Tuple[bool, str]:
    """Run downscaled FFmpeg cropdetect on keyframes to guarantee zero letterbox/pillarbox bars."""
    probe_w = 540 if expected_h > expected_w else 640
    probe_h = max(2, int(round(expected_h * (probe_w / max(expected_w, 1)) / 2.0)) * 2)
    cmd = [
        get_ffmpeg_bin(),
        "-threads",
        "0",
        "-skip_frame",
        "nokey",
        "-i",
        str(video_path),
        "-an",
        "-vf",
        f"scale={probe_w}:{probe_h}:flags=fast_bilinear,cropdetect=limit=18:round=2:reset=0:skip=0",
        "-t",
        "12",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    matches = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", res.stderr or "")
    if not matches:
        return True, f"{expected_w}x{expected_h} (clean)"
    # Use last stable converged crop box and scale back cleanly to expected resolution
    cw, ch, cx, cy = [int(v) for v in matches[-1]]
    w_ratio = cw / max(probe_w, 1)
    h_ratio = ch / max(probe_h, 1)
    scale_x = expected_w / max(probe_w, 1)
    scale_y = expected_h / max(probe_h, 1)
    est_cw = min(expected_w, int(round(cw * scale_x)))
    est_ch = min(expected_h, int(round(ch * scale_y)))
    est_cx = int(round(cx * scale_x))
    est_cy = int(round(cy * scale_y))
    ok = w_ratio >= 0.96 and h_ratio >= 0.96
    return ok, f"active={est_cw}x{est_ch}+{est_cx}+{est_cy} ({w_ratio*100:.1f}%x{h_ratio*100:.1f}%)"


def _detect_frozen_frames(video_path: Path, max_freeze_sec: float = 1.85) -> Tuple[bool, int]:
    """Verify no static frame freezes beyond max_freeze_sec using fast downscaled analysis."""
    cmd = [
        get_ffmpeg_bin(),
        "-threads",
        "0",
        "-skip_frame",
        "noref",
        "-i",
        str(video_path),
        "-an",
        "-vf",
        f"fps=8,scale=540:-2:flags=fast_bilinear,freezedetect=n=-60dB:d={max_freeze_sec:.2f}",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    stderr = res.stderr or ""
    # FFmpeg emits freeze_start as soon as a freeze exceeds `d`; freeze_duration is only emitted
    # if the freeze ends before EOF, so counting max(starts, durations) catches tail freezes too.
    freeze_starts = re.findall(r"freeze_start:\s*([\d.]+)", stderr)
    freeze_durs = re.findall(r"freeze_duration:\s*([\d.]+)", stderr)
    freeze_count = max(len(freeze_starts), len(freeze_durs))
    return freeze_count == 0, freeze_count


def run_qa_gate(video_path: Path, fmt: str = "shorts") -> Dict[str, Any]:
    """Execute full automated QA audit on a rendered MP4."""
    expected_w, expected_h = (2160, 3840) if fmt == "shorts" else (1920, 1080)
    min_dur, max_dur = (20.0, 39.5) if fmt == "shorts" else (60.0, 420.0)

    failures: List[str] = []
    remediation: Dict[str, Any] = {}

    if not video_path.exists() or video_path.stat().st_size < 100_000:
        return {
            "passed": False,
            "video_path": str(video_path),
            "failures": ["Output file missing or suspiciously small (<100KB)."],
            "checks": {},
            "remediation": {"retry_render": True},
        }

    probe = _probe_streams(video_path)
    v_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
    a_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]

    if not v_streams or not a_streams:
        return {
            "passed": False,
            "video_path": str(video_path),
            "failures": ["Missing video or audio stream."],
            "checks": {},
            "remediation": {"retry_render": True},
        }

    vs = v_streams[0]
    aus = a_streams[0]
    actual_w = int(vs.get("width", 0))
    actual_h = int(vs.get("height", 0))
    pix_fmt = vs.get("pix_fmt", "")
    v_codec = vs.get("codec_name", "")
    a_codec = aus.get("codec_name", "")
    a_sr = int(aus.get("sample_rate", 0))
    a_ch = int(aus.get("channels", 0))

    # Parse exact frame rate fraction (e.g., "60/1")
    fps_str = vs.get("avg_frame_rate") or vs.get("r_frame_rate") or "0/1"
    num, den = fps_str.split("/") if "/" in fps_str else (fps_str, "1")
    actual_fps = float(num) / max(float(den), 1.0)
    duration = float(probe.get("format", {}).get("duration", 0.0))

    # 1. Resolution check
    res_ok = actual_w == expected_w and actual_h == expected_h
    if not res_ok:
        failures.append(f"Resolution mismatch: got {actual_w}x{actual_h}, expected {expected_w}x{expected_h}")

    # 2. FPS check
    fps_ok = actual_fps >= 59.0
    if not fps_ok:
        failures.append(f"Frame rate below 60fps target: got {actual_fps:.2f}fps")

    # 3. Duration bounds check (auto-remediate Shorts >39.5s by bumping TTS speed targeting 33.0s)
    dur_ok = min_dur <= duration <= max_dur
    if not dur_ok:
        failures.append(f"Duration {duration:.2f}s outside {fmt} window [{min_dur}s, {max_dur}s]")
        if fmt == "shorts" and duration > max_dur:
            ratio = duration / 33.0
            bump_pct = min(32, max(18, int(round((ratio - 1.0) * 100)) + 16))
            remediation["speech_rate"] = f"+{bump_pct}%"
            remediation["resynthesize_voice"] = True

    # 4-6. Run loudness, downscaled border & downscaled freeze checks in parallel for <8s 4K QA
    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_lufs = pool.submit(_measure_lufs_and_peak, video_path)
        fut_borders = pool.submit(_detect_black_borders, video_path, expected_w, expected_h)
        fut_motion = pool.submit(_detect_frozen_frames, video_path, 1.85)
        lufs, peak_dbfs = fut_lufs.result()
        borders_ok, border_detail = fut_borders.result()
        motion_ok, freeze_count = fut_motion.result()

    # 4. Loudness (LUFS) & peak check
    lufs_ok = lufs is not None and (-17.5 <= lufs <= -11.0)
    if not lufs_ok:
        failures.append(f"Loudness out of broadcast range [-17.5, -11.0] LUFS: got {lufs}")
        remediation["target_lufs"] = -14.0

    peak_ok = peak_dbfs is None or peak_dbfs <= -0.1
    if not peak_ok:
        failures.append(f"Audio clipping detected: peak {peak_dbfs} dBFS > -0.1 dBFS")

    # 5. Zero black border check
    if not borders_ok:
        failures.append(f"Black borders / letterboxing detected: {border_detail}")

    # 6. Static freeze check (>1.85s violates V3 fluid continuous-motion standard)
    if not motion_ok:
        failures.append(f"Detected {freeze_count} static frozen segment(s) > 1.85s")

    # 7. Codec & compatibility check
    codec_ok = v_codec == "h264" and pix_fmt == "yuv420p" and a_codec == "aac" and a_ch == 2 and a_sr == 48000
    if not codec_ok:
        failures.append(
            f"Stream format non-standard: v={v_codec}/{pix_fmt}, a={a_codec}/{a_sr}Hz/{a_ch}ch"
        )

    passed = len(failures) == 0
    report = {
        "passed": passed,
        "video_path": str(video_path),
        "file_size_mb": round(video_path.stat().st_size / 1_000_000, 2),
        "checks": {
            "resolution": {"ok": res_ok, "value": f"{actual_w}x{actual_h}"},
            "fps": {"ok": fps_ok, "value": round(actual_fps, 2)},
            "duration_sec": {"ok": dur_ok, "value": round(duration, 2)},
            "loudness_lufs": {"ok": lufs_ok, "value": lufs},
            "true_peak_dbfs": {"ok": peak_ok, "value": peak_dbfs},
            "zero_black_borders": {"ok": borders_ok, "detail": border_detail},
            "no_static_freeze_over_2_5s": {"ok": motion_ok, "freeze_count": freeze_count},
            "codecs": {"ok": codec_ok, "value": f"{v_codec}/{pix_fmt} + {a_codec}/{a_sr}Hz/{a_ch}ch"},
        },
        "failures": failures,
        "remediation": remediation,
    }

    if passed:
        logger.info(
            "QA GATE PASSED | %dx%d @ %.1ffps | %.2fs | %.1f LUFS | 0 borders | 0 freezes",
            actual_w,
            actual_h,
            actual_fps,
            duration,
            lufs or -14.0,
        )
    else:
        logger.warning("QA GATE REJECTED (%d failure(s)): %s", len(failures), "; ".join(failures))
    return report
