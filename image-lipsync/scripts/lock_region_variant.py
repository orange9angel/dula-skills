#!/usr/bin/env python3
"""Diff an imagegen local edit against its base frame, then feather-lock it back.

Computes the pixel-difference bounding box between base and variant, validates
that the drift is confined (small area, single region), and composites the
variant's differing region back onto the base with a feathered mask — so every
pixel outside the edit is guaranteed identical to the base.

Prints the final rect as `RECT x y w h` for copy-paste into rig configs.

Usage:
    python tools/lock_region_variant.py BASE VARIANT OUTPUT \
        --margin 10 --feather 8 --max-area-frac 0.02
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("variant", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--margin", type=int, default=10,
                        help="pixels added around the diff bbox")
    parser.add_argument("--feather", type=float, default=8.0)
    parser.add_argument("--threshold", type=int, default=12,
                        help="per-channel difference counted as a changed pixel")
    parser.add_argument("--window", nargs=4, type=int, default=None,
                        metavar=("X", "Y", "W", "H"),
                        help="restrict diff detection to this region; use when the "
                             "raw generation carries global low-level re-encode noise")
    parser.add_argument("--max-area-frac", type=float, default=0.02,
                        help="reject if diff bbox exceeds this fraction of the image")
    args = parser.parse_args()

    base = Image.open(args.base).convert("RGB")
    variant = Image.open(args.variant).convert("RGB")
    if variant.size != base.size:
        raise SystemExit(
            f"SIZE MISMATCH: variant {variant.size} vs base {base.size} — edit drifted"
        )

    diff = ImageChops.difference(base, variant)
    gray = diff.convert("L")
    if args.window:
        wx, wy, ww, wh = args.window
        clipped = Image.new("L", base.size, 0)
        clipped.paste(gray.crop((wx, wy, wx + ww, wy + wh)), (wx, wy))
        gray = clipped
    mask_small = gray.point(lambda v: 255 if v > args.threshold else 0)
    bbox = mask_small.getbbox()
    if bbox is None:
        raise SystemExit("NO DIFF: variant is pixel-identical to base — edit did nothing")

    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - args.margin)
    y0 = max(0, y0 - args.margin)
    x1 = min(base.width, x1 + args.margin)
    y1 = min(base.height, y1 + args.margin)
    width, height = x1 - x0, y1 - y0
    area_frac = (width * height) / (base.width * base.height)
    changed = sum(1 for v in mask_small.getdata() if v)
    print(f"diff bbox: ({x0}, {y0}, {width}, {height}) "
          f"changed_px={changed} bbox_area_frac={area_frac:.5f}")
    if area_frac > args.max_area_frac:
        raise SystemExit(
            f"DRIFT: diff bbox covers {area_frac:.4%} of the image "
            f"(limit {args.max_area_frac:.4%}) — edit is not local, rejecting"
        )

    mask = Image.new("L", base.size, 0)
    draw = ImageDraw.Draw(mask)
    inset = max(2, round(args.feather * 1.25))
    draw.rounded_rectangle(
        (x0 + inset, y0 + inset, x1 - inset, y1 - inset),
        radius=max(2, round(min(width, height) * 0.18)),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius=args.feather))
    locked = Image.composite(variant, base, mask)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    locked.save(args.output, format="PNG", optimize=True)

    # Post-lock verification: outside the bbox + feather pad the locked image
    # must be pixel-identical to the base.
    locked_diff = ImageChops.difference(base, locked).convert("L")
    pad = round(args.feather * 3)
    inner = ImageDraw.Draw(locked_diff)
    inner.rectangle((x0 - pad, y0 - pad, x1 + pad, y1 + pad), fill=0)
    if locked_diff.getbbox() is not None:
        raise SystemExit("LEAK: locked variant still differs outside the feather zone")
    print(f"RECT {x0} {y0} {width} {height}")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
