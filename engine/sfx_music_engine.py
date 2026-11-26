"""Autonomous Procedural Cinema SFX & Dark Documentary Underscore Engine.

Synthesizes 100% royalty-free, copyright-safe, broadcast-grade 48kHz stereo audio
using NumPy + SciPy DSP:
- sub_boom: Deep 88Hz->32Hz sub-bass drop + transient impact (0-2s Shock Hook)
- whoosh:   Stereo bandpass sweep for crisp 2.5s visual cuts
- tick:     Precision Bloomberg/telemetry clock transient
- sonar:    Dark Vox-documentary resonant data ping
- glitch:   Short digital anomaly burst
- riser:    Subtle tension filter swell into key reveals
- tension_bed: Duration-matched Hans-Zimmer/Vox dark minor pulse underscore
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Dict

import numpy as np
from scipy.signal import butter, sosfilt

from core.config import get_logger

logger = get_logger("sfx_music_engine")

SAMPLE_RATE = 48000


def _write_stereo_wav(path: Path, stereo: np.ndarray, sr: int = SAMPLE_RATE) -> Path:
    """Write float32 [-1, 1] stereo array (N, 2) to 16-bit PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = float(np.max(np.abs(stereo))) if stereo.size else 1.0
    if peak > 0.96:
        stereo = stereo * (0.96 / peak)
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return path


def _bandpass(sig: np.ndarray, low_hz: float, high_hz: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    nyq = sr * 0.5
    low = max(20.0, min(low_hz, nyq - 100.0)) / nyq
    high = max(low + 0.01, min(high_hz, nyq - 50.0) / nyq)
    sos = butter(3, [low, high], btype="bandpass", output="sos")
    return sosfilt(sos, sig)


def _lowpass(sig: np.ndarray, cutoff_hz: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    nyq = sr * 0.5
    norm = max(20.0, min(cutoff_hz, nyq - 50.0)) / nyq
    sos = butter(4, norm, btype="lowpass", output="sos")
    return sosfilt(sos, sig)


def synth_sub_boom(duration: float = 1.15) -> np.ndarray:
    """Deep cinematic sub-bass impact drop (88Hz -> 33Hz) + punch transient."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # Exponential frequency glide
    freq = 33.0 + 62.0 * np.exp(-t * 7.5)
    phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    sub = np.sin(phase) * np.exp(-t * 3.1)
    # Warm harmonic saturation
    sub_warm = np.tanh(sub * 1.9) * 0.85

    # Initial air-punch transient (first 70ms)
    rng = np.random.default_rng(101)
    burst = rng.normal(0, 1, n) * np.exp(-t * 38.0)
    punch = _lowpass(burst, 480.0) * 0.65

    # Subtle stereo width on upper air layer
    air_l = _bandpass(rng.normal(0, 1, n), 160.0, 900.0) * np.exp(-t * 14.0) * 0.22
    air_r = _bandpass(rng.normal(0, 1, n), 160.0, 900.0) * np.exp(-t * 14.0) * 0.22

    attack = np.clip(t / 0.008, 0.0, 1.0)
    left = (sub_warm + punch + air_l) * attack
    right = (sub_warm + punch + air_r) * attack
    return np.stack([left, right], axis=1)


def synth_whoosh(duration: float = 0.42) -> np.ndarray:
    """Crisp stereo-swept transition whoosh for fast 2.5s visual cuts."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    rng = np.random.default_rng(202)
    noise = rng.normal(0, 1, n)

    # Bell-shaped amplitude envelope peaking slightly past midpoint
    env = np.sin(np.pi * (t / duration) ** 0.85) ** 1.8
    # Multi-band blend simulating swept resonant air
    low_band = _bandpass(noise, 180.0, 620.0) * (1.0 - t / duration)
    mid_band = _bandpass(noise, 550.0, 1800.0) * env
    high_band = _bandpass(noise, 1400.0, 3600.0) * (t / duration) * env

    body = (low_band * 0.6 + mid_band * 0.9 + high_band * 0.45) * env * 0.72
    # Gentle left-to-right stereo pan
    pan = np.linspace(0.32, 0.68, n)
    left = body * np.cos(pan * np.pi * 0.5) * 1.4
    right = body * np.sin(pan * np.pi * 0.5) * 1.4
    return np.stack([left, right], axis=1)


def synth_tick(duration: float = 0.14) -> np.ndarray:
    """Precision telemetry counter click / Bloomberg clock pulse."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    click = (
        np.sin(2 * np.pi * 1680.0 * t) * np.exp(-t * 75.0) * 0.55
        + np.sin(2 * np.pi * 3420.0 * t) * np.exp(-t * 115.0) * 0.35
        + np.sin(2 * np.pi * 420.0 * t) * np.exp(-t * 48.0) * 0.35
    )
    attack = np.clip(t / 0.002, 0.0, 1.0)
    sig = click * attack * 0.75
    return np.stack([sig, sig * 0.94], axis=1)


def synth_sonar(duration: float = 0.95) -> np.ndarray:
    """Dark investigative documentary data ping with stereo decay."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    attack = np.clip(t / 0.006, 0.0, 1.0)
    ping_l = (
        np.sin(2 * np.pi * 880.0 * t) * np.exp(-t * 4.4)
        + 0.32 * np.sin(2 * np.pi * 1318.5 * t) * np.exp(-t * 6.0)
    ) * attack * 0.48
    ping_r = (
        np.sin(2 * np.pi * 882.2 * t) * np.exp(-t * 4.2)
        + 0.30 * np.sin(2 * np.pi * 1320.0 * t) * np.exp(-t * 5.8)
    ) * attack * 0.48
    return np.stack([ping_l, ping_r], axis=1)


def synth_glitch(duration: float = 0.24) -> np.ndarray:
    """Crisp digital anomaly stutter hit."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    rng = np.random.default_rng(404)
    carrier = np.sign(np.sin(2 * np.pi * 240.0 * t)) * 0.25
    noise = _bandpass(rng.normal(0, 1, n), 1200.0, 5200.0) * 0.45
    # Stutter gate at 42Hz
    gate = (np.sin(2 * np.pi * 42.0 * t) > -0.15).astype(np.float32)
    env = np.exp(-t * 11.0) * gate
    l = (carrier + noise) * env * 0.65
    r = (carrier * 0.8 + np.roll(noise, 180)) * env * 0.65
    return np.stack([l, r], axis=1)


def synth_riser(duration: float = 1.2) -> np.ndarray:
    """Cinematic tension sweep riser into major reveal."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    prog = t / duration
    freq = 110.0 * (2.0 ** (prog * 2.1))
    phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    tone = np.sin(phase) * (prog**1.8) * 0.38
    rng = np.random.default_rng(505)
    air = _bandpass(rng.normal(0, 1, n), 600.0, 3800.0) * (prog**2.2) * 0.32
    fade_out = np.clip((duration - t) / 0.04, 0.0, 1.0)
    sig = (tone + air) * fade_out
    return np.stack([sig, sig * 0.96], axis=1)


def synth_xray_scan(duration: float = 0.52) -> np.ndarray:
    """VELUM V8.1 signature sci-fi X-Ray laser sweep + crisp mechanical lock impact."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    prog = t / duration
    # Descending dual-harmonic laser scan beam (1950Hz -> 420Hz)
    freq = 1950.0 * (0.215 ** (prog ** 0.78))
    phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    laser = (
        0.42 * np.sin(phase)
        + 0.22 * np.sin(phase * 1.503)
    ) * np.sin(np.pi * prog) ** 0.75
    # High-tech crisp air whoosh riding the laser line
    rng = np.random.default_rng(808)
    air = _bandpass(rng.normal(0, 1, n), 900.0, 4800.0) * np.sin(np.pi * prog) ** 1.3 * 0.42
    # Deep tactile latch thump at lock-in (t=0.04s)
    latch = np.sin(2.0 * np.pi * 68.0 * t) * np.exp(-t * 14.0) * 0.58
    attack = np.clip(t / 0.006, 0.0, 1.0)
    left = (laser + air * 0.9 + latch) * attack * 0.85
    right = (laser * 0.95 + np.roll(air, 120) * 0.9 + latch) * attack * 0.85
    return np.stack([left, right], axis=1)


def synth_tension_bed(duration: float) -> np.ndarray:
    """Synthesize a dark, pulsing Netflix/Vox documentary underscore bed (D minor, 120 BPM)."""
    total_dur = max(5.0, float(duration) + 1.2)
    n = int(SAMPLE_RATE * total_dur)
    t = np.linspace(0, total_dur, n, endpoint=False)

    # 1. Deep evolving D1/A1 cinematic sub-drone (36.71Hz & 55Hz & 73.42Hz)
    lfo = 0.72 + 0.28 * np.sin(2 * np.pi * 0.14 * t)
    drone = (
        0.48 * np.sin(2 * np.pi * 36.71 * t)
        + 0.32 * np.sin(2 * np.pi * 73.42 * t + 0.3 * np.sin(2 * np.pi * 0.2 * t))
        + 0.18 * np.sin(2 * np.pi * 110.0 * t)
    ) * lfo
    drone = _lowpass(drone, 240.0)

    # 2. Dark atmospheric D-minor suspended pad (D3, F3, A3, E4 with stereo detune)
    pad_lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.09 * t - 0.7)
    pad_l = (
        0.22 * np.sin(2 * np.pi * 146.83 * t)
        + 0.16 * np.sin(2 * np.pi * 174.61 * t)
        + 0.18 * np.sin(2 * np.pi * 220.00 * t)
        + 0.10 * np.sin(2 * np.pi * 329.63 * t)
    ) * pad_lfo
    pad_r = (
        0.22 * np.sin(2 * np.pi * 147.25 * t + 0.4)
        + 0.16 * np.sin(2 * np.pi * 174.20 * t + 0.9)
        + 0.18 * np.sin(2 * np.pi * 220.55 * t + 1.2)
        + 0.10 * np.sin(2 * np.pi * 329.10 * t + 0.6)
    ) * pad_lfo
    pad_l = _lowpass(pad_l, 950.0)
    pad_r = _lowpass(pad_r, 950.0)

    # 3. 120 BPM subtle investigative pulse + muted precision clock tick (every 0.5s)
    beat_period = 0.5
    beat_phase = np.mod(t, beat_period)
    pulse_env = np.exp(-beat_phase * 14.0)
    bass_pulse = np.sin(2 * np.pi * 73.42 * t) * pulse_env * 0.24

    # Accent every 4th beat slightly stronger
    bar_accent = np.where(np.mod(t, 2.0) < 0.5, 1.35, 0.80)
    tick_phase = np.mod(t, 0.25)
    tick_env = np.exp(-tick_phase * 85.0)
    clock_tick = np.sin(2 * np.pi * 1920.0 * t) * tick_env * 0.055 * bar_accent

    # Smooth fade-in and fade-out
    fade_in = np.clip(t / 0.6, 0.0, 1.0)
    fade_out = np.clip((total_dur - t) / 1.0, 0.0, 1.0)
    env = fade_in * fade_out

    left = (drone * 0.55 + pad_l * 0.55 + bass_pulse + clock_tick) * env
    right = (drone * 0.55 + pad_r * 0.55 + bass_pulse + clock_tick * 0.85) * env
    stereo = np.stack([left, right], axis=1)

    # Soft limiter normalization to comfortable underscore headroom
    peak = float(np.max(np.abs(stereo))) or 1.0
    return stereo / peak * 0.72


def generate_audio_pack(work_dir: Path, total_duration: float) -> Dict[str, Path]:
    """Generate the complete royalty-free SFX kit and duration-matched tension bed."""
    sfx_dir = work_dir / "audio_assets"
    sfx_dir.mkdir(parents=True, exist_ok=True)

    assets = {
        "sub_boom": _write_stereo_wav(sfx_dir / "sub_boom.wav", synth_sub_boom()),
        "whoosh": _write_stereo_wav(sfx_dir / "whoosh.wav", synth_whoosh()),
        "tick": _write_stereo_wav(sfx_dir / "tick.wav", synth_tick()),
        "sonar": _write_stereo_wav(sfx_dir / "sonar.wav", synth_sonar()),
        "glitch": _write_stereo_wav(sfx_dir / "glitch.wav", synth_glitch()),
        "riser": _write_stereo_wav(sfx_dir / "riser.wav", synth_riser()),
        "xray_scan": _write_stereo_wav(sfx_dir / "xray_scan.wav", synth_xray_scan()),
        "tension_bed": _write_stereo_wav(sfx_dir / "tension_bed.wav", synth_tension_bed(total_duration)),
    }
    logger.info(
        "Synthesized Autonomous cinema audio pack (%d SFX + %.1fs tension bed)",
        len(assets) - 1,
        total_duration,
    )
    return assets
