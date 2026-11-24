"""Edge-TTS + FFmpeg silenceremove + Faster-Whisper Word-Level Alignment Engine.

Pipeline:
1. Synthesizes studio documentary voiceover via free Edge-TTS neural voices.
2. Applies FFmpeg `silenceremove` + broadcast vocal clarity EQ to eliminate dead air.
3. Runs `faster-whisper` (word_timestamps=True) on the cleaned audio to obtain
   frame-exact word start/end timings for kinetic word-by-word captions.
4. Maps script beats onto exact audio timestamps and splits any beat >2.5s so
   no visual frame ever remains static beyond the 2.5-second rhythm law.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import wave
from pathlib import Path
from typing import Any, Dict, List, Tuple

import edge_tts
import numpy as np

from core.config import get_ffmpeg_bin, get_ffprobe_bin, get_logger, load_brand_config

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
logger = get_logger("voice_engine")


def _probe_duration(media_path: Path) -> float:
    cmd = [
        get_ffprobe_bin(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)


async def _synthesize_edge_tts_async(
    text: str, voice: str, out_mp3: Path, rate: str = "+16%", pitch: str = "+0Hz"
) -> List[Dict[str, Any]]:
    """Synthesize speech with Edge-TTS with automatic multi-voice fallback and backoff retry."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    candidate_voices = [
        voice,
        "en-US-BrianMultilingualNeural",
        "en-US-AndrewMultilingualNeural",
        "en-US-ChristopherNeural",
        "en-US-GuyNeural",
        "en-US-SteffanNeural",
    ]
    # Deduplicate while preserving order
    unique_voices: List[str] = []
    for v in candidate_voices:
        if v and v not in unique_voices:
            unique_voices.append(v)

    max_attempts = 6
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        active_voice = unique_voices[min(attempt - 1, len(unique_voices) - 1)]
        active_pitch = pitch if attempt <= 2 else "+0Hz"
        word_boundaries: List[Dict[str, Any]] = []
        try:
            if out_mp3.exists():
                out_mp3.unlink()
            communicate = edge_tts.Communicate(
                text=text, voice=active_voice, rate=rate, pitch=active_pitch
            )
            with open(out_mp3, "wb") as fh:
                async for chunk in communicate.stream():
                    ctype = chunk.get("type")
                    if ctype == "audio":
                        fh.write(chunk["data"])
                    elif ctype == "WordBoundary":
                        start_s = chunk["offset"] / 10_000_000.0
                        dur_s = chunk["duration"] / 10_000_000.0
                        word_boundaries.append(
                            {
                                "word": chunk["text"].strip(),
                                "start": round(start_s, 3),
                                "end": round(start_s + max(0.06, dur_s), 3),
                            }
                        )
            if out_mp3.exists() and out_mp3.stat().st_size >= 1024:
                if attempt > 1:
                    logger.info(
                        "Edge-TTS succeeded on retry #%d using voice=%s (%d bytes)",
                        attempt,
                        active_voice,
                        out_mp3.stat().st_size,
                    )
                return word_boundaries
            raise RuntimeError(f"Edge-TTS produced empty/tiny audio file ({out_mp3})")
        except Exception as exc:
            last_error = exc
            wait_s = 1.8 * attempt
            logger.warning(
                "Edge-TTS attempt %d/%d failed (voice=%s, err=%s); retrying in %.1fs...",
                attempt,
                max_attempts,
                active_voice,
                exc,
                wait_s,
            )
            await asyncio.sleep(wait_s)

    raise RuntimeError(f"Edge-TTS failed after {max_attempts} attempts: {last_error}") from last_error


def _clean_voice_with_silenceremove(raw_mp3: Path, clean_wav: Path) -> float:
    """Apply tight FFmpeg silenceremove (0.00s instant hook + zero-gap loop) + studio vocal clarity EQ."""
    ffmpeg = get_ffmpeg_bin()
    af_chain = (
        "highpass=f=80,"
        "silenceremove=start_periods=1:start_duration=0.015:start_threshold=-38dB:"
        "stop_periods=-1:stop_duration=0.08:stop_threshold=-35dB,"
        "areverse,silenceremove=start_periods=1:start_duration=0.015:start_threshold=-38dB,areverse,"
        "acompressor=threshold=-17dB:ratio=3.5:attack=6:release=95:makeup=2.8,"
        "equalizer=f=180:t=q:w=1.0:g=1.6,"
        "equalizer=f=3400:t=q:w=1.2:g=2.6,"
        "alimiter=limit=0.95,"
        "aresample=48000"
    )
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(raw_mp3),
        "-af",
        af_chain,
        "-ac",
        "2",
        "-ar",
        "48000",
        "-c:a",
        "pcm_s16le",
        str(clean_wav),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return _probe_duration(clean_wav)


def _load_wav_as_16k_mono_float32(wav_path: Path) -> np.ndarray:
    """Read 48kHz PCM WAV via stdlib wave and downsample cleanly to 16kHz mono float32 for Whisper."""
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1)
    if sr == 16000:
        return pcm
    if sr == 48000:
        # Clean boxcar average every 3 samples (anti-aliased 48k -> 16k)
        trim_len = (len(pcm) // 3) * 3
        return pcm[:trim_len].reshape(-1, 3).mean(axis=1).astype(np.float32)
    target_len = max(1, int(round(len(pcm) * 16000.0 / sr)))
    x_old = np.linspace(0.0, 1.0, len(pcm), endpoint=False)
    x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
    return np.interp(x_new, x_old, pcm).astype(np.float32)


def _extract_whisper_word_timestamps(clean_wav: Path, lang: str = "en") -> List[Dict[str, Any]]:
    """Run faster-whisper on the post-silenceremove audio (16kHz NumPy array) for exact word timings."""
    try:
        from faster_whisper import WhisperModel

        model_name = "tiny.en" if lang == "en" else "tiny"
        logger.info("Running faster-whisper (%s, int8 CPU) for word-level alignment...", model_name)
        audio_16k = _load_wav_as_16k_mono_float32(clean_wav)
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            audio_16k,
            language=lang,
            word_timestamps=True,
            vad_filter=False,
            beam_size=1,
        )
        words: List[Dict[str, Any]] = []
        for seg in segments:
            if not seg.words:
                continue
            for w in seg.words:
                token = (w.word or "").strip()
                if not token:
                    continue
                start = max(0.0, float(w.start))
                end = max(start + 0.05, float(w.end))
                words.append({"word": token, "start": round(start, 3), "end": round(end, 3)})
        if words:
            logger.info("Whisper aligned %d words accurately.", len(words))
            return words
    except Exception as exc:
        logger.warning("Whisper alignment fallback triggered (%s); scaling Edge-TTS boundaries.", exc)
    return []


def _scale_fallback_words(
    raw_words: List[Dict[str, Any]], raw_dur: float, clean_dur: float
) -> List[Dict[str, Any]]:
    """Proportionally remap Edge-TTS word boundaries if Whisper is offline."""
    if not raw_words or raw_dur <= 0:
        return []
    scale = clean_dur / raw_dur
    scaled: List[Dict[str, Any]] = []
    for w in raw_words:
        s = round(max(0.0, w["start"] * scale), 3)
        e = round(min(clean_dur, max(s + 0.06, w["end"] * scale)), 3)
        scaled.append({"word": w["word"], "start": s, "end": e})
    return scaled


def _align_beats_to_audio(
    beats: List[Dict[str, Any]], words: List[Dict[str, Any]], total_dur: float, fmt: str = "shorts"
) -> List[Dict[str, Any]]:
    """Map script beats onto real spoken audio times and enforce tight V5 viral cut rhythm."""
    max_beat_sec = 1.78 if fmt == "shorts" else 2.48
    split_divisor = 1.64 if fmt == "shorts" else 2.25
    # Compute cumulative word counts per beat to anchor exact time spans
    beat_word_counts = [max(1, len(re.findall(r"\S+", b["narration"]))) for b in beats]
    total_script_words = sum(beat_word_counts)

    raw_timed: List[Dict[str, Any]] = []
    cursor_time = 0.0
    word_cursor = 0
    total_aligned = len(words)

    for idx, (beat, wcount) in enumerate(zip(beats, beat_word_counts)):
        is_last = idx == len(beats) - 1
        if is_last:
            end_time = total_dur
        elif total_aligned >= total_script_words * 0.65:
            next_idx = min(total_aligned - 1, int(round((word_cursor + wcount) * total_aligned / total_script_words)))
            end_time = float(words[next_idx]["end"])
            end_time = max(cursor_time + 1.0, min(total_dur - 0.5 * (len(beats) - idx - 1), end_time))
        else:
            share = total_dur * (wcount / max(total_script_words, 1))
            end_time = min(total_dur, cursor_time + share)

        entry = dict(beat)
        entry["start"] = round(cursor_time, 3)
        entry["end"] = round(max(cursor_time + 0.8, end_time), 3)
        raw_timed.append(entry)
        cursor_time = entry["end"]
        word_cursor += wcount

    if raw_timed:
        raw_timed[-1]["end"] = round(total_dur, 3)

    # Enforce strict visual cut rhythm (<= 2.08s on Shorts, <= 2.48s on Long-form)
    rhythm_beats: List[Dict[str, Any]] = []
    motions = ["zoom_in", "pan_right", "zoom_out", "pan_left", "drift_up"]
    sub_idx = 0
    for b_idx, b in enumerate(raw_timed):
        dur = b["end"] - b["start"]
        is_final_beat = b_idx == len(raw_timed) - 1
        if dur <= max_beat_sec:
            sub_idx += 1
            item = dict(b)
            item["index"] = sub_idx
            item["duration"] = round(dur, 3)
            rhythm_beats.append(item)
        else:
            pieces = max(2, int(dur / split_divisor) + 1)
            step = dur / pieces
            for p in range(pieces):
                sub_idx += 1
                s = round(b["start"] + p * step, 3)
                e = round(b["end"] if p == pieces - 1 else b["start"] + (p + 1) * step, 3)
                clone = dict(b)
                clone["index"] = sub_idx
                clone["start"] = s
                clone["end"] = e
                clone["duration"] = round(e - s, 3)
                # Alternate motion & visual variety on sub-cut so frame never stays static or shows truncated text
                if p > 0:
                    clone["camera_motion"] = motions[(sub_idx + p) % len(motions)]
                    clone["sfx"] = "tick" if p % 2 == 1 else "whoosh"
                    # Preserve closing debate CTA card on the very last sub-piece
                    if is_final_beat and p == pieces - 1 and b.get("plate_mode") == "debate_cta_plate":
                        clone["visual_type"] = "data_plate"
                    else:
                        # V5 Cinema-First: sub-cuts ALWAYS switch to vivid moving HD B-roll (zero truncated radar text!)
                        clone["visual_type"] = "photo_grade"
                        clone["plate_data"] = {}
                rhythm_beats.append(clone)

    # V5 Cinema-First Frame-0 Lock: Beat 0 ALWAYS opens on vivid full-bleed HD footage (photo_grade)
    # so the V5 floating cover headline pops cleanly over real moving cinema with zero box clutter!
    if rhythm_beats and fmt == "shorts":
        rhythm_beats[0]["visual_type"] = "photo_grade"

    # Recompute monotonic HUD progress 0..1 across all visual beats
    n_total = max(len(rhythm_beats), 1)
    for i, rb in enumerate(rhythm_beats):
        rb["hud_progress"] = round((i + 1) / n_total, 3)

    return rhythm_beats


def synthesize_voice_and_align(
    script: Dict[str, Any],
    work_dir: Path,
    lang: str = "en",
    speech_rate: str | None = None,
) -> Dict[str, Any]:
    """Generate Edge-TTS voiceover, strip silence, extract Whisper word timings, and align beats."""
    brand = load_brand_config()
    voice = brand.get("voices", {}).get(lang, "en-US-BrianMultilingualNeural")
    fmt = script.get("format", "shorts")
    effective_rate = speech_rate or ("+18%" if fmt == "shorts" else "+10%")
    narration_text = script["full_narration"]

    voice_dir = work_dir / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    raw_mp3 = voice_dir / "narration_raw.mp3"
    clean_wav = voice_dir / "narration_clean.wav"

    logger.info("Synthesizing Edge-TTS voiceover (%s, rate=%s)...", voice, effective_rate)
    raw_boundaries = asyncio.run(
        _synthesize_edge_tts_async(narration_text, voice, raw_mp3, rate=effective_rate)
    )
    raw_dur = _probe_duration(raw_mp3)

    clean_dur = _clean_voice_with_silenceremove(raw_mp3, clean_wav)
    logger.info(
        "Voice cleaned via FFmpeg silenceremove: %.2fs -> %.2fs (removed %.2fs dead air)",
        raw_dur,
        clean_dur,
        max(0.0, raw_dur - clean_dur),
    )

    words = _extract_whisper_word_timestamps(clean_wav, lang=lang)
    if not words:
        words = _scale_fallback_words(raw_boundaries, raw_dur, clean_dur)

    # Guarantee final fallback if both Whisper & WordBoundary produced nothing
    if not words:
        tokens = narration_text.split()
        step = clean_dur / max(len(tokens), 1)
        words = [
            {"word": tok, "start": round(i * step, 3), "end": round((i + 1) * step, 3)}
            for i, tok in enumerate(tokens)
        ]

    timed_beats = _align_beats_to_audio(script["beats"], words, clean_dur, fmt=fmt)
    max_beat = max((b["duration"] for b in timed_beats), default=0.0)
    logger.info(
        "Aligned %d visual beats across %.2fs (max single shot: %.2fs)",
        len(timed_beats),
        clean_dur,
        max_beat,
    )

    alignment_path = voice_dir / "alignment.json"
    result = {
        "voice": voice,
        "raw_mp3": str(raw_mp3),
        "clean_wav": str(clean_wav),
        "duration": round(clean_dur, 3),
        "words": words,
        "timed_beats": timed_beats,
    }
    alignment_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
