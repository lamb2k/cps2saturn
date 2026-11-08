#!/usr/bin/env python3
"""Compare an emulator's audio capture with a MAME reference of the same script. Needs numpy.

Inputs: REF.wav (MAME, 16-bit stereo) and CAP (raw s16le stereo, or a .wav), both 44.1 kHz.
Reports silence share, best offset by 10 ms envelope alignment, whole-envelope correlation, level difference in dB,
and the median correlation over 1 s windows that have sound.
Tier: EMULATOR output against MAME. Not a listening test and not hardware.

usage: audio_compare.py REF.wav CAP [--ref-start SECONDS] [--rate 44100]
"""
from __future__ import annotations

import argparse
import sys
import wave

import numpy as np


def load_wav(path: str) -> np.ndarray:
    with wave.open(path) as w:
        if w.getsampwidth() != 2:
            raise ValueError("16-bit WAV only")
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        return a.reshape(-1, w.getnchannels()).astype(np.float32)


def load(path: str) -> np.ndarray:
    if path.lower().endswith(".wav"):
        return load_wav(path)
    return np.fromfile(path, dtype="<i2").reshape(-1, 2).astype(np.float32)


def envelope(x: np.ndarray, step: int = 441) -> np.ndarray:
    n = len(x) // step
    if n == 0:
        return np.zeros(0)
    sq = (x[:n * step].astype(np.float64) ** 2).mean(axis=1)
    return np.sqrt(sq.reshape(n, step).mean(axis=1))


def compare(ref: np.ndarray, cap: np.ndarray) -> dict:
    er, ec = envelope(ref), envelope(cap)
    n = min(len(er), 3000)
    a = er[:n]
    span = max(1, len(ec) - n + 1)
    best = max(range(span), key=lambda d: float(np.dot(a, ec[d:d + n])))
    b = ec[best:best + n]
    if len(b) < n:
        b = np.pad(b, (0, n - len(b)))
    corr = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
    windows = []
    for s in range(0, n - 100 + 1, 100):
        x, y = a[s:s + 100], b[s:s + 100]
        if x.max() > 200 and x.std() > 0 and y.std() > 0:
            windows.append(float(np.corrcoef(x, y)[0, 1]))
    return dict(
        offset_s=best / 100, envelope_corr=round(corr, 3),
        level_db=round(20 * float(np.log10((b.mean() + 1) / (a.mean() + 1))), 1),
        sound_windows=len(windows), median_window_corr=round(float(np.median(windows)), 3) if windows else None,
        capture_sound_pct=round(100 * float((ec > 32).mean()), 1) if len(ec) else 0.0,
        ref_sound_pct=round(100 * float((er > 32).mean()), 1) if len(er) else 0.0,
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("cap")
    ap.add_argument("--ref-start", type=float, default=0.0)
    ap.add_argument("--rate", type=int, default=44100)
    a = ap.parse_args(argv)
    ref = load_wav(a.ref)[int(a.ref_start * a.rate):]
    cap = load(a.cap)
    print(f"seconds capture {len(cap) / a.rate:.1f} ref {len(ref) / a.rate:.1f}")
    for k, v in compare(ref, cap).items():
        print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
