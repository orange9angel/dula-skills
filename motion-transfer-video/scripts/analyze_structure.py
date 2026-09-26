#!/usr/bin/env python3
"""Structural dissection of beat-edit (卡点) tracks vs our V5 music.

For each input wav/mp4, reports:
  - duration, BPM (kick-grid based)
  - kick onsets (<150 Hz spectral flux) + accent positions (strong kicks)
  - RMS curve stats: drop point (largest +RMS step), pre-drop silence gap
    (dip below -18dB of track RMS for 0.1-0.5s right before the drop),
    drop jump size in dB
  - low-band (<150 Hz) energy share, high-band (>5 kHz) onset density
  - spectral centroid mean (timbre brightness hint)

Usage (from dula-story):
  .venv/Scripts/python.exe ../dula-skills/motion-transfer-video/scripts/analyze_structure.py \
      file1.wav file2.wav ... --out report.json
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
HIGH_HZ = 5000.0


def load_mono(path: Path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f",
                          "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def spectrogram(y):
    frames = np.array([y[i:i + NFFT] for i in range(0, len(y) - NFFT, HOP)])
    win = np.hanning(NFFT)
    return np.abs(np.array([np.fft.rfft(f * win) for f in frames]))


def band_flux(mags, lo_hz, hi_hz):
    bin_hz = SR / NFFT
    lo, hi = int(lo_hz / bin_hz), max(int(hi_hz / bin_hz), int(lo_hz / bin_hz) + 1)
    flux = np.maximum(0.0, np.diff(mags[:, lo:hi], axis=0)).sum(axis=1)
    return (flux - flux.mean()) / (flux.std() + 1e-9)


def pick_onsets(flux, pct=85, min_gap_s=0.22):
    thresh = np.percentile(flux, pct)
    min_gap = int(min_gap_s * SR / HOP)
    out, last = [], -min_gap * 2
    for i in range(1, len(flux) - 1):
        if flux[i] > thresh and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] \
                and i - last >= min_gap:
            out.append((round(i * HOP / SR, 4), float(flux[i])))
            last = i
    return out


def rms_curve(y, win_s=0.05):
    n = int(win_s * SR)
    m = len(y) // n
    frames = y[:m * n].reshape(m, n)
    return np.sqrt((frames ** 2).mean(axis=1)), win_s


def find_drop(rms, win_s):
    """Largest positive RMS step + pre-drop silence gap check."""
    db = 20 * np.log10(rms / (rms.max() + 1e-9) + 1e-9)
    steps = np.diff(db)
    di = int(steps.argmax())
    drop_t = round((di + 1) * win_s, 2)
    jump_db = round(float(steps[di]), 1)
    # scan backwards up to 1.0s for a dip below -18dB lasting >=0.1s
    gap_len, gap_t = 0.0, None
    run = 0
    for i in range(di, max(0, di - int(1.0 / win_s)), -1):
        if db[i] < -18:
            run += 1
        else:
            if run * win_s >= 0.1 and gap_t is None:
                gap_len, gap_t = run * win_s, round(i * win_s, 2)
            run = 0
    if run * win_s >= 0.1 and gap_t is None:
        gap_len, gap_t = run * win_s, round(max(0, di - run) * win_s, 2)
    return {"drop_t": drop_t, "drop_jump_db": jump_db,
            "pre_drop_gap_s": round(gap_len, 2), "gap_at": gap_t}


def analyze(path: Path) -> dict:
    y = load_mono(path)
    dur = round(len(y) / SR, 2)
    mags = spectrogram(y)

    kicks = pick_onsets(band_flux(mags, 0, LOW_HZ), pct=85, min_gap_s=0.25)
    highs = pick_onsets(band_flux(mags, HIGH_HZ, SR / 2), pct=88, min_gap_s=0.10)
    kt = np.array([t for t, _ in kicks])
    ks = np.array([s for _, s in kicks])

    bpm = None
    if len(kt) >= 4:
        iv = np.diff(kt)
        iv = iv[(iv >= 0.25) & (iv <= 2.0)]
        if len(iv):
            bpm = 60.0 / float(np.median(iv))
            while bpm < 70:
                bpm *= 2
            while bpm > 180:
                bpm /= 2
            bpm = round(bpm, 1)

    accents = kt[ks >= np.percentile(ks, 60)] if len(kt) else np.array([])
    rms, win_s = rms_curve(y)
    drop = find_drop(rms, win_s)

    bin_hz = SR / NFFT
    e = (mags ** 2).sum(axis=0)
    low_share = round(float(e[:int(LOW_HZ / bin_hz)].sum() / e.sum()), 3)
    freqs = np.fft.rfftfreq(NFFT, 1 / SR)
    centroid = round(float((mags * freqs).sum() / (mags.sum() + 1e-9)), 0)

    # RMS contour: 14 coarse buckets for the report
    buckets = np.array_split(rms, 14)
    contour = [round(float(20 * np.log10(b.mean() + 1e-9)), 1) for b in buckets]

    return {
        "file": str(path),
        "duration_s": dur,
        "bpm": bpm,
        "kicks": len(kicks),
        "accent_times": [round(float(t), 2) for t in accents],
        "accent_count": len(accents),
        "high_onsets": len(highs),
        "high_onsets_per_s": round(len(highs) / dur, 1),
        "low_energy_share": low_share,
        "spectral_centroid_hz": centroid,
        "drop": drop,
        "rms_contour_db": contour,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out")
    args = ap.parse_args()
    results = []
    for f in args.files:
        r = analyze(f)
        results.append(r)
        d = r["drop"]
        print(f"{Path(f).name}: {r['duration_s']}s bpm={r['bpm']} "
              f"kicks={r['kicks']} accents={r['accent_count']} "
              f"hi/s={r['high_onsets_per_s']} low%={r['low_energy_share']} "
              f"centroid={r['spectral_centroid_hz']}Hz "
              f"drop@{d['drop_t']}s(+{d['drop_jump_db']}dB, "
              f"gap {d['pre_drop_gap_s']}s@{d['gap_at']})")
    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False,
                                             indent=2), encoding="utf-8")
        print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
