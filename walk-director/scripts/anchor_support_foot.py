#!/usr/bin/env python3
"""Anchor a passing cel's ground plane to the contact cel (post-process).

Two-step composite, distilled from walk_skill_test v1-v8:

1. `--box`: paste the contact cel's planted shoe + contact shadow through a
   tight feathered box. Generation-side anchoring ("keep the planted foot
   pixel-exact") suppresses the swing (v12: support 2.3% but swing 27%->3.6%),
   so anchor in post instead.
2. `--band y0,y1,x0,x1` (optional but usually needed): unify the ground band
   below the feet — paste the contact cel's road + cast shadow over the
   passing cel's, EXCLUDING a dilated neighborhood of the dark shoe/sock
   pixels so the swinging foot keeps its own soft contact shadow. Without
   this the cast-shadow shape flips between cels and reads as background
   jitter next to the calves; with a plain luminance exclusion (no dilation)
   the half-pasted soft shadow becomes a white smudge (v7 mistake).

Box discipline: the step-1 box must cover ONLY the planted shoe + its contact
shadow — touching the swing foot's shadow blends two shadow shapes into a
fuzzy blob (v3 mistake).

Usage (from dula-story root):
    python ../dula-skills/walk-director/scripts/anchor_support_foot.py \
      <contact.png> <passing.png> <out.png> --box 640,765,725,885 \
      --band 790,895,560,790 \
      --support-zone 650,740,800,880 --swing-zone 540,740,650,880
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_box(text):
    parts = [int(v) for v in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x0,y0,x1,y1")
    return parts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contact", type=Path, help="contact cel (anchor source)")
    parser.add_argument("passing", type=Path, help="passing cel (big swing)")
    parser.add_argument("out", type=Path, help="output composited cel")
    parser.add_argument("--box", type=parse_box, required=True,
                        help="x0,y0,x1,y1: planted shoe + contact shadow only")
    parser.add_argument("--radius", type=int, default=14)
    parser.add_argument("--feather", type=int, default=6)
    parser.add_argument("--band", type=parse_box, default=None,
                        help="y0,y1,x0,x1 ground band to unify (road + cast shadow)")
    parser.add_argument("--dark-threshold", type=int, default=120,
                        help="mean luminance below this counts as shoe/sock")
    parser.add_argument("--dark-dilate", type=int, default=21,
                        help="pixels to grow the dark exclusion (keeps the swing "
                             "foot's soft shadow; too small leaves a white smudge)")
    parser.add_argument("--support-zone", type=parse_box, default=None,
                        help="report diff%% vs contact in this zone (expect < 3%%)")
    parser.add_argument("--swing-zone", type=parse_box, default=None,
                        help="report diff%% vs contact in this zone (expect large)")
    args = parser.parse_args(argv)

    try:
        from PIL import Image, ImageDraw, ImageFilter
        import numpy as np
    except ImportError:
        print("ERROR: requires Pillow and numpy", file=sys.stderr)
        return 2

    contact = Image.open(args.contact).convert("RGB")
    passing = Image.open(args.passing).convert("RGB")
    if contact.size != passing.size:
        print(f"ERROR: size mismatch {contact.size} vs {passing.size}", file=sys.stderr)
        return 2
    width, height = contact.size

    # step 1: planted shoe + contact shadow anchor
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(args.box, radius=args.radius, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(args.feather))
    out = passing.copy()
    out.paste(contact, (0, 0), mask)

    # step 2: ground-band unify, keeping dark shoes/socks and their soft shadows
    if args.band:
        y0, y1, x0, x1 = args.band
        arr = np.asarray(out).astype(np.float32)
        lum = arr.mean(axis=2)
        dark = Image.fromarray(((lum < args.dark_threshold) * 255).astype(np.uint8))
        dark = dark.filter(ImageFilter.MaxFilter(args.dark_dilate))
        dark_np = np.asarray(dark).astype(np.float32) / 255.0
        band = np.zeros((height, width), np.float32)
        band[y0:y1, x0:x1] = 1.0
        mask2_np = band * (1.0 - dark_np)
        mask2 = Image.fromarray((mask2_np * 255).astype(np.uint8))
        mask2 = mask2.filter(ImageFilter.GaussianBlur(3))
        out.paste(contact, (0, 0), mask2)

    out.save(args.out)

    if args.support_zone or args.swing_zone:
        a = np.asarray(contact).astype(np.float32)
        o = np.asarray(out).astype(np.float32)
        diff = np.abs(a - o).sum(axis=2)
        for name, zone in (("support", args.support_zone), ("swing", args.swing_zone)):
            if zone:
                zx0, zy0, zx1, zy1 = zone
                r = diff[zy0:zy1, zx0:zx1]
                print(f"{name} zone vs contact: changed>30 {(r > 30).mean() * 100:.2f}% "
                      f"mean {r.mean():.1f}")

    print(f"OK: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
