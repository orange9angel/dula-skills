#!/usr/bin/env python3
"""Auto-lock locally-edited variants back onto their base frames.

For each variant PNG (mouth/eye), diff against the base frame, take the
changed-region bbox (expanded + feathered), composite only that region onto
the base, and verify zero change outside. Output: *_locked_v1.png next to the
variant. Mirrors the rainy_rooftop_cat lock_region_variant.py discipline
(PIL pixel diff, change confined to a small rect) but auto-detects the rect.

Usage: python auto_lock_variants.py [EPISODE_DIR]      # batch mode
       python auto_lock_variants.py --base B --variant V --output O [--rect x,y,w,h]
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

THRESH = 30
EXPAND = 12
FEATHER = 6


def collect(episode_dir: Path) -> list:
    keyframes = episode_dir / "assets" / "keyframes"
    pairs = []  # (base, variant_path)
    mv = episode_dir / "assets" / "mouth_variants"
    ev = episode_dir / "assets" / "eye_variants"
    for d in (mv, ev):
        if not d.exists():
            continue
        for v in sorted(d.glob("*.png")):
            if v.stem.endswith("_locked_v1"):
                continue
            base_name = v.stem.split("_")[0] + "_" + v.stem.split("_")[1]  # frame_XX
            base = keyframes / f"{base_name}.png"
            if base.exists():
                pairs.append((base, v))
            else:
                print(f"SKIP {v.name}: base {base_name}.png not found")
    return pairs


def lock_one(base_path: Path, variant_path: Path, output_path=None, rect_override=None):
    base = Image.open(base_path).convert("RGB")
    var = Image.open(variant_path).convert("RGB")
    if var.size != base.size:
        var = var.resize(base.size)
    w, h = base.size
    if rect_override:
        x0, y0, rw, rh = rect_override
        x1, y1 = x0 + rw, y0 + rh
        if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
            print(f"FAIL {variant_path.name}: rect outside {w}x{h}: {rect_override}")
            return False
    else:
        diff = ImageChops.difference(base, var)
        mask = diff.convert("L").point(lambda p: 255 if p > THRESH else 0)
        bbox = mask.getbbox()
        if not bbox:
            print(f"FAIL {variant_path.name}: no change detected")
            return False
        x0, y0, x1, y1 = bbox
        x0, y0 = max(0, x0 - EXPAND), max(0, y0 - EXPAND)
        x1, y1 = min(w, x1 + EXPAND), min(h, y1 + EXPAND)
    rect = (x0, y0, x1, y1)

    region_mask = Image.new("L", base.size, 0)
    region_mask.paste(255, rect)
    region_mask = region_mask.filter(ImageFilter.GaussianBlur(FEATHER))

    locked = Image.composite(var, base, region_mask)
    out = Path(output_path) if output_path else variant_path.with_name(variant_path.stem + "_locked_v1.png")
    locked.save(out)

    # verify: outside rect + feather halo, locked must equal base exactly
    check = ImageChops.difference(base, locked).convert("L")
    inv = Image.new("L", base.size, 255)
    # GaussianBlur has a very faint tail beyond 2 sigma; exclude a 4x feather
    # halo so the strict outside-region check measures only genuinely untouched pixels.
    halo = (max(0, x0 - 4 * FEATHER), max(0, y0 - 4 * FEATHER),
            min(w, x1 + 4 * FEATHER), min(h, y1 + 4 * FEATHER))
    inv.paste(0, halo)
    outside = ImageChops.multiply(check, inv)
    extrema = outside.getextrema()
    area = (x1 - x0) * (y1 - y0)
    ok = extrema[1] == 0
    print(f"{'OK  ' if ok else 'FAIL'} {variant_path.name}: rect={rect} "
          f"({area / (w * h) * 100:.1f}% of frame), outside max diff={extrema[1]}")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_dir", nargs="?", default=Path.cwd(), type=Path,
                        help="batch mode: episode root containing assets/keyframes, "
                             "assets/mouth_variants, assets/eye_variants (default: cwd)")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--variant", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rect", help="explicit x,y,width,height region to feather-lock")
    args = parser.parse_args()
    if args.base or args.variant or args.output or args.rect:
        if not (args.base and args.variant and args.output):
            parser.error("--base, --variant and --output are required together")
        rect = tuple(map(int, args.rect.split(","))) if args.rect else None
        if rect and len(rect) != 4:
            parser.error("--rect must be x,y,width,height")
        return 0 if lock_one(args.base, args.variant, args.output, rect) else 1

    pairs = collect(args.episode_dir.resolve())
    if not pairs:
        print("no variants to lock")
        return 0
    fails = sum(0 if lock_one(b, v) else 1 for b, v in pairs)
    print(f"locked {len(pairs) - fails}/{len(pairs)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
