#!/usr/bin/env python3
"""Calibrate config/mouth_rigs.json and config/eye_rigs.json from the real
locked variants: diff each *_locked_v1.png against its base keyframe, then take
the DENSE-core bbox of the change (5x5 density filter), expanded 14 px.

Why density filtering (V1.1, 2026-08-30): Seedream variants regenerate the
whole frame, so the locked image carries sparse regen noise inside the paste
box (shifted hair edges etc.). A plain threshold-30 bbox inflates to the whole
face box and the cel swap then visibly jitters the whole face. The intended
edit (mouth interior / closed lids) is a dense high-contrast cluster; noise is
sparse and thin. Keep only pixels whose 5x5 neighbourhood has >=10 changed
pixels, then bbox the remainder. Codex variants are bit-clean outside the
edit, so the density filter returns the same tight rects for them.

Run after tools/auto_lock_variants.py / gen_variants_seedream.py.
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

EP = Path(__file__).resolve().parent.parent
A = EP / "assets"
THRESH = 30
DENSITY_MIN = 10  # changed pixels required within a 5x5 window
EXPAND = 14

MOUTH_RIGS = {  # rig name -> (base frame, story entry)
    "girl_frame01_entry3": ("frame_01", 3),
    "girl_frame04_entry7": ("frame_04", 7),
    "girl_frame06_entry10": ("frame_06", 10),
    "girl_frame11_entry14": ("frame_11", 14),
    "girl_frame16_entry17": ("frame_16", 17),
    "cat_frame02_entry4": ("frame_02", 4),
    "cat_frame08_entry11": ("frame_08", 11),
    "cat_frame12_entry15": ("frame_12", 15),
}

EYE_RIGS = {  # rig name -> base frame
    "girl_frame01_blink": "frame_01",
    "girl_frame03_blink": "frame_03",
    "girl_frame04_blink": "frame_04",
    "girl_frame06_blink": "frame_06",
    "girl_frame11_blink": "frame_11",
    "girl_frame13_blink": "frame_13",
    "girl_frame14_blink": "frame_14",
    "girl_frame16_blink": "frame_16",
    "cat_frame02_blink": "frame_02",
    "cat_frame08_blink": "frame_08",
    "cat_frame12_blink": "frame_12",
}


def diff_bbox(base: Image.Image, variant: Image.Image) -> tuple[int, int, int, int]:
    """Dense-core diff bbox; falls back to the plain bbox if nothing is dense."""
    if variant.size != base.size:
        variant = variant.resize(base.size)
    diff = np.asarray(ImageChops.difference(base, variant).convert("L"))
    mask = (diff > THRESH).astype(np.uint8)
    padded = np.pad(mask, 2)
    windows = np.lib.stride_tricks.sliding_window_view(padded, (5, 5))
    dense = windows.sum(axis=(-2, -1)) >= DENSITY_MIN
    ys, xs = np.where(dense)
    if len(xs) == 0:  # fallback: plain bbox (codex-clean variants always dense)
        ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        raise RuntimeError("no diff bbox found")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def union(boxes: list[tuple[int, int, int, int]], w: int, h: int) -> list[int]:
    x0 = max(0, min(b[0] for b in boxes) - EXPAND)
    y0 = max(0, min(b[1] for b in boxes) - EXPAND)
    x1 = min(w, max(b[2] for b in boxes) + EXPAND)
    y1 = min(h, max(b[3] for b in boxes) + EXPAND)
    return [x0, y0, x1 - x0, y1 - y0]


def main() -> None:
    mouth_rigs = {}
    for rig, (base_name, entry) in MOUTH_RIGS.items():
        base = Image.open(A / "keyframes" / f"{base_name}.png").convert("RGB")
        half = A / "mouth_variants" / f"{base_name}_half_locked_v1.png"
        open_ = A / "mouth_variants" / f"{base_name}_open_locked_v1.png"
        boxes = [diff_bbox(base, Image.open(p).convert("RGB")) for p in (half, open_)]
        rect = union(boxes, *base.size)
        mouth_rigs[rig] = {
            "entry": entry,
            "mode": "image",
            "rect": rect,
            "variants": {
                "closed": f"keyframes/{base_name}.png",
                "half": f"mouth_variants/{base_name}_half_locked_v1.png",
                "open": f"mouth_variants/{base_name}_open_locked_v1.png",
            },
        }
        print(f"mouth {rig}: rect={rect}")
    (EP / "config" / "mouth_rigs.json").write_text(json.dumps({
        "version": 2,
        "sourceCoordinateSpace": "native-image-pixels",
        "states": ["closed", "half", "open"],
        "notes": ("Only the tight mouth rectangle is copied from generated variants; "
                  "all other pixels come from the stable closed-mouth base frame. "
                  "Variants are the feather-locked outputs of tools/auto_lock_variants.py "
                  "(codex auto-bbox) or gen_variants_seedream.py (explicit face rect). "
                  "Rects calibrated by tools/build_rigs.py with dense-core diff bboxes "
                  "(threshold 30 + 5x5 density >=10), unioned over half+open, expanded "
                  "14px — density filtering keeps Seedream regen noise from inflating "
                  "the rig rect (V1 face-jitter fix)."),
        "rigs": mouth_rigs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    eye_rigs = {}
    for rig, base_name in EYE_RIGS.items():
        base = Image.open(A / "keyframes" / f"{base_name}.png").convert("RGB")
        closed = A / "eye_variants" / f"{base_name}_closed_locked_v1.png"
        rect = union([diff_bbox(base, Image.open(closed).convert("RGB"))], *base.size)
        eye_rigs[rig] = {
            "rect": rect,
            "closed": f"eye_variants/{base_name}_closed_locked_v1.png",
            "intervalSeconds": [2.8, 4.4],
        }
        print(f"eye   {rig}: rect={rect}")
    (EP / "config" / "eye_rigs.json").write_text(json.dumps({
        "version": 1,
        "sourceCoordinateSpace": "native-image-pixels",
        "notes": ("Blink rigs. The closed variant is feather-locked onto the base frame "
                  "(tools/auto_lock_variants.py); only the rect region is copied during "
                  "a blink. Interval is per-rig randomized by the scene's deterministic "
                  "scheduler (full-name hash stagger). Rects calibrated by "
                  "tools/build_rigs.py with dense-core diff bboxes (threshold 30 + 5x5 "
                  "density >=10), expanded 14px."),
        "rigs": eye_rigs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote config/mouth_rigs.json + config/eye_rigs.json")


if __name__ == "__main__":
    main()
