#!/usr/bin/env python3
"""Composite an imagegen mouth edit back onto a pixel-locked base frame."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("variant", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rect", nargs=4, type=int, required=True, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--feather", type=float, default=8.0)
    args = parser.parse_args()

    base = Image.open(args.base).convert("RGB")
    variant = Image.open(args.variant).convert("RGB")
    if variant.size != base.size:
        raise ValueError(f"Variant size {variant.size} does not match base {base.size}")

    x, y, width, height = args.rect
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > base.width or y + height > base.height:
        raise ValueError(f"Mouth rect {args.rect} is outside {base.size}")

    mask = Image.new("L", base.size, 0)
    draw = ImageDraw.Draw(mask)
    inset = max(2, round(args.feather * 1.25))
    draw.rounded_rectangle(
        (x + inset, y + inset, x + width - inset, y + height - inset),
        radius=max(2, round(min(width, height) * 0.18)),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius=args.feather))
    locked = Image.composite(variant, base, mask)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    locked.save(args.output, format="PNG", optimize=True)
    print(f"Wrote pixel-locked mouth variant: {args.output}")


if __name__ == "__main__":
    main()
