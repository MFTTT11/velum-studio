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
    text: str, voice: str, out_mp3: Path, rate: str = "+12%", pitch: str = "-1Hz"
) -> List[Dict[str, Any]]:
    """Synthesize speech with Edge-TTS and capture native WordBoundary events as backup."""
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    word_boundaries: List[Dict[str, Any]] = []
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
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
    return word_boundaries


def _clean_voice_with_silenceremove(raw_mp3: Path, clean_wav: Path) -> float:
    """Apply FFmpeg silenceremove + documentary vocal presence EQ to 48kHz stereo WAV."""
    ffmpeg = get_ffmpeg_bin()
    af_chain = (
        "highpass=f=75,"
        "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB:"
        "stop_periods=-1:stop_duration=0.16:stop_threshold=-38dB,"
        "acompressor=threshold=-18dB:ratio=3.2:attack=8:release=110:makeup=2.5,"
        "equalizer=f=3200:t=q:w=1.2:g=2.2,"
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
    beats: List[Dict[str, Any]], words: List[Dict[str, Any]], total_dur: float
) -> List[Dict[str, Any]]:
    """Map script beats onto real spoken audio times and enforce the <=2.5s visual rhythm rule."""
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

    # Enforce strict <= 2.5s visual beat rule by subdividing any beat longer than 2.45s
    rhythm_beats: List[Dict[str, Any]] = []
    motions = ["zoom_in", "pan_right", "zoom_out", "pan_left", "drift_up"]
    sub_idx = 0
    for b in raw_timed:
        dur = b["end"] - b["start"]
        if dur <= 2.48:
            sub_idx += 1
            item = dict(b)
            item["index"] = sub_idx
            item["duration"] = round(dur, 3)
            rhythm_beats.append(item)
        else:
            pieces = max(2, int(dur / 2.25) + 1)
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
                # Alternate motion & visual variety on sub-cut so frame never stays static or generic
                if p > 0:
                    clone["camera_motion"] = motions[(sub_idx + p) % len(motions)]
                    clone["sfx"] = "tick" if p % 2 == 1 else "whoosh"
                    if clone["visual_type"] == "data_plate":
                        clone["visual_type"] = "photo_grade"
                    else:
                        # Only flip photo -> data_plate with rich beat-specific telemetry (never empty!)
                        if not clone.get("plate_data"):
                            raw_narr = clone.get("narration", "").strip()
                            sub_words: List[str] = []
                            for w_tok in raw_narr.split():
                                if len(" ".join(sub_words + [w_tok])) <= 48:
                                    sub_words.append(w_tok)
                                else:
                                    break
                            clean_sub = " ".join(sub_words).rstrip(".,;:-—").upper()
                            clean_title = clone.get("hud_tag", "LIVE TELEMETRY").replace("//", "·")
                            clone["plate_mode"] = "metric_hero" if p % 2 == 1 else "radar_alert"
                            clone["plate_data"] = {
                                "title": clean_title,
                                "hero_value": clone.get("hud_metric", "VERIFIED"),
                                "metric": clone.get("hud_metric", "VERIFIED"),
                                "subtitle": clean_sub,
                                "severity": clone.get("hud_delta", "SIGNAL"),
                                "accent": "amber" if sub_idx % 2 == 0 else "cyan",
                            }
                        clone["visual_type"] = "data_plate"
                rhythm_beats.append(clone)

    # Keep Beat 1 as a high-contrast animated data plate at 0.0s (positioned below the 0-2s Shock Hook)
    # so viewers immediately see both the Shock Hook banner and the visual comparison chart on Frame 0!
    if rhythm_beats and rhythm_beats[0]["visual_type"] != "data_plate" and rhythm_beats[0].get("plate_data"):
        rhythm_beats[0]["visual_type"] = "data_plate"

    # Recompute monotonic HUD progress 0..1 across all visual beats
    n_total = max(len(rhythm_beats), 1)
    for i, rb in enumerate(rhythm_beats):
        rb["hud_progress"] = round((i + 1) / n_total, 3)

    return rhythm_beats


def synthesize_voice_and_align(
    script: Dict[str, Any],
    work_dir: Path,
    lang: str = "en",
    speech_rate: str = "+12%",
) -> Dict[str, Any]:
    """Generate Edge-TTS voiceover, strip silence, extract Whisper word timings, and align beats."""
    brand = load_brand_config()
    voice = brand.get("voices", {}).get(lang, "en-US-AndrewMultilingualNeural")
    narration_text = script["full_narration"]

    voice_dir = work_dir / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    raw_mp3 = voice_dir / "narration_raw.mp3"
    clean_wav = voice_dir / "narration_clean.wav"

    logger.info("Synthesizing Edge-TTS voiceover (%s, rate=%s)...", voice, speech_rate)
    raw_boundaries = asyncio.run(
        _synthesize_edge_tts_async(narration_text, voice, raw_mp3, rate=speech_rate)
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

    timed_beats = _align_beats_to_audio(script["beats"], words, clean_dur)
    max_beat = max((b["duration"] for b in timed_beats), default=0.0)
    logger.info(
        "Aligned %d visual beats across %.2fs (max single shot: %.2fs <= 2.50s)",
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
