#!/usr/bin/env python3
"""Kick/accent analysis for downloaded Douyin candidates.

Low-band (<150 Hz) spectral-flux onset detection — same FFT/flux approach as
beatcut-edit/scripts/beatcut.py::detect_onsets, but restricted to the kick
band. Reports per video: duration, BPM estimate, total kicks, and the number
of usable accents inside the best 14 s window (accent = kick with strength
above the 60th percentile of all kicks).

Usage (from dula-story):
  .venv/Scripts/python.exe ../dula-skills/motion-transfer-video/scripts/analyze_beats.py \
      tmp/douyin/videos/*.mp4 --out tmp/douyin/beats.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 44100
HOP, NFFT = 512, 2048
LOW_HZ = 150.0
WINDOW_S = 14.0


def load_mono(path: Path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f",
                          "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def duration_of(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def detect_kicks(samples: np.ndarray):
    """Low-band (<150 Hz) spectral flux -> [(t_seconds, strength)]."""
    if len(samples) < NFFT * 2:
        return []
    frames = [samples[i:i + NFFT] for i in range(0, len(samples) - NFFT, HOP)]
    win = np.hanning(NFFT)
    mags = np.abs(np.array([np.fft.rfft(f * win) for f in frames]))
    bins = int(LOW_HZ / (SR / NFFT)) + 1
    flux = np.maximum(0.0, np.diff(mags[:, :bins], axis=0)).sum(axis=1)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    thresh = np.percentile(flux, 85)
    min_gap = int(0.25 * SR / HOP)
    out, last = [], -min_gap * 2
    for i in range(1, len(flux) - 1):
        if flux[i] > thresh and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] \
                and i - last >= min_gap:
            out.append((round(i * HOP / SR, 4), float(flux[i])))
            last = i
    return out


def estimate_bpm(times: np.ndarray) -> float | None:
    if len(times) < 4:
        return None
    iv = np.diff(times)
    iv = iv[(iv >= 0.25) & (iv <= 2.0)]
    if len(iv) == 0:
        return None
    bpm = 60.0 / float(np.median(iv))
    while bpm < 70:
        bpm *= 2
    while bpm > 180:
        bpm /= 2
    return round(bpm, 1)


def best_window_accents(onsets, window: float = WINDOW_S) -> tuple[int, float]:
    """Max count of strong kicks (>= p60 strength) in any `window`-s span."""
    if not onsets:
        return 0, 0.0
    times = np.array([t for t, _ in onsets])
    strs = np.array([s for _, s in onsets])
    strong = times[strs >= np.percentile(strs, 60)]
    if len(strong) == 0:
        return 0, 0.0
    best, best_t = 0, float(strong[0])
    j = 0
    for i, t in enumerate(strong):
        while strong[j] < t - window:
            j += 1
        if i - j + 1 > best:
            best, best_t = i - j + 1, float(strong[j])
    return best, round(best_t, 2)


def analyze(path: Path) -> dict:
    samples = load_mono(path)
    onsets = detect_kicks(samples)
    times = np.array([t for t, _ in onsets])
    accents, win_start = best_window_accents(onsets)
    return {
        "file": path.name,
        "duration_s": round(duration_of(path), 2),
        "bpm": estimate_bpm(times),
        "kicks": len(onsets),
        "accents_in_14s": accents,
        "best_14s_start": win_start,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", help="write JSON results here")
    args = ap.parse_args()

    results = []
    for f in args.files:
        try:
            r = analyze(f)
        except Exception as e:
            print(f"ERROR {f}: {e}", file=sys.stderr)
            continue
        results.append(r)
        print(f"{r['file']}: dur={r['duration_s']}s bpm={r['bpm']} "
              f"kicks={r['kicks']} accents14s={r['accents_in_14s']} "
              f"(window@{r['best_14s_start']}s)")
    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False,
                                             indent=2), encoding="utf-8")
        print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
