#!/usr/bin/env python3
"""Re-lock mouth variants with tight per-frame lip windows (v2).

For each (frame, state): sanity-check that the threshold-45 diff bbox inside
the tight window does not touch the window edge (which would mean the mouth
diff spills past the window), then run tools/lock_region_variant.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

EPISODE = Path(__file__).resolve().parents[1]
PY = sys.executable

# Tight lip-zone windows (x, y, w, h) picked from grid-annotated base crops;
# they exclude the chin/jaw contour shift and hair/beard re-encode noise that
# inflated the v1 rig rects.
WINDOWS = {
    "frame_01": (778, 360, 172, 80),
    "frame_02": (838, 204, 96, 56),
    "frame_03": (896, 484, 128, 72),
    "frame_04": (640, 214, 62, 48),
    "frame_05": (700, 372, 140, 110),
    "frame_06": (682, 338, 118, 56),
    "frame_07": (774, 268, 70, 40),
    "frame_09": (910, 312, 88, 62),
    "frame_10": (780, 618, 280, 78),
}

STATES = {
    "frame_01": ["closed", "half", "open"],
    "frame_02": ["half", "open"],
    "frame_03": ["closed", "half", "open"],
    "frame_04": ["half", "open"],
    "frame_05": ["closed", "half", "open"],
    "frame_06": ["half", "open"],
    "frame_07": ["half", "open"],
    "frame_09": ["closed", "half", "open"],
    "frame_10": ["half", "open"],
}

THRESHOLD = 45


def main() -> int:
    failures = 0
    rects: dict[str, list[tuple[int, int, int, int]]] = {}
    for frame, states in STATES.items():
        wx, wy, ww, wh = WINDOWS[frame]
        base = Image.open(EPISODE / "assets" / "keyframes" / f"{frame}.png").convert("RGB")
        for state in states:
            variant_path = EPISODE / "tmp" / "variants_raw" / f"{frame}_mouth_{state}.png"
            variant = Image.open(variant_path).convert("RGB")
            gray = ImageChops.difference(base, variant).convert("L")
            mask = gray.point(lambda v: 255 if v > THRESHOLD else 0)
            clipped = Image.new("L", base.size, 0)
            clipped.paste(mask.crop((wx, wy, wx + ww, wy + wh)), (wx, wy))
            raw_bbox = clipped.getbbox()
            tag = f"{frame} {state}"
            if raw_bbox is None:
                print(f"[{tag}] FAIL: no diff above threshold {THRESHOLD} inside window")
                failures += 1
                continue
            rx0, ry0, rx1, ry1 = raw_bbox
            touches = (
                rx0 <= wx or ry0 <= wy or rx1 >= wx + ww or ry1 >= wy + wh
            )
            print(
                f"[{tag}] raw bbox=({rx0},{ry0},{rx1 - rx0},{ry1 - ry0}) "
                f"inside window ({wx},{wy},{ww},{wh})"
                + ("  ** TOUCHES WINDOW EDGE **" if touches else "")
            )
            out = EPISODE / "assets" / "mouth_variants" / f"{frame}_mouth_{state}_locked_v2.png"
            result = subprocess.run(
                [
                    PY, str(EPISODE / "tools" / "lock_region_variant.py"),
                    str(EPISODE / "assets" / "keyframes" / f"{frame}.png"),
                    str(variant_path), str(out),
                    "--window", str(wx), str(wy), str(ww), str(wh),
                    "--threshold", str(THRESHOLD),
                    "--margin", "14", "--feather", "6",
                    "--max-area-frac", "0.05",
                ],
                capture_output=True, text=True,
            )
            rect_line = next(
                (l for l in result.stdout.splitlines() if l.startswith("RECT ")), None
            )
            if result.returncode != 0 or rect_line is None:
                print(f"[{tag}] LOCK FAILED:\n{result.stdout}{result.stderr}")
                failures += 1
                continue
            _, x, y, w, h = rect_line.split()
            rects.setdefault(frame, []).append((int(x), int(y), int(w), int(h)))
            print(f"[{tag}] {rect_line} -> {out.name}")

    print("\nUnion rects per rig (for mouth_rigs.json):")
    for frame, items in rects.items():
        x0 = min(r[0] for r in items)
        y0 = min(r[1] for r in items)
        x1 = max(r[0] + r[2] for r in items)
        y1 = max(r[1] + r[3] for r in items)
        print(f"  {frame}_mouth: [{x0}, {y0}, {x1 - x0}, {y1 - y0}]  (n={len(items)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
