#!/usr/bin/env python3
"""Re-lock Seedream variants with TIGHT feature boxes (V1.1 face-jitter fix).

V1 locked Seedream variants with whole-face boxes; the rig rect then covered
regen noise across the face, so every mouth/blink cel swap visibly jittered
the whole face box. This re-locks the same raw variants with small boxes that
hug the mouth / eyes. auto_lock feathers the box edge, and everything outside
stays bit-identical to the base frame by construction.

Rects: (x, y, w, h) on the 1672x941 base frames. Auto ones come from the
t=60 + 3x3-erosion dense-diff analysis; hand ones were measured on crops
(cat fur and the frame_16 close-up regen too densely for auto-detection).
Codex-made variants (frame_01/04 mouths) keep their original tight locks.
"""

import sys
from pathlib import Path

EP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EP / "tools"))
from auto_lock_variants import lock_one  # noqa: E402

K = EP / "assets" / "keyframes"
MV = EP / "assets" / "mouth_variants"
EV = EP / "assets" / "eye_variants"

# Mouth boxes: seedream frames only (01/04 are codex-locked already).
MOUTH_BOX = {
    "frame_06": (678, 258, 41, 58),    # auto t=60 eroded + 12px
    "frame_11": (483, 168, 40, 47),    # auto
    "frame_02": (609, 368, 49, 38),    # auto (cat)
    "frame_16": (698, 483, 60, 60),    # hand (profile close-up lips)
    "frame_08": (1105, 355, 70, 55),   # hand (cat)
    "frame_12": (775, 325, 80, 60),    # hand (cat)
}

# Blink boxes: all 11 (blinks were all seedream).
EYE_BOX = {
    "frame_01": (441, 276, 91, 70),    # auto clipped
    "frame_03": (558, 183, 85, 70),    # auto clipped
    "frame_04": (700, 120, 100, 80),   # auto clipped
    "frame_06": (666, 194, 52, 51),    # auto clipped (profile, one eye)
    "frame_11": (471, 127, 56, 44),    # auto clipped
    "frame_13": (471, 200, 58, 52),    # auto clipped
    "frame_14": (712, 191, 51, 50),    # auto clipped
    "frame_16": (645, 270, 75, 75),    # hand (close-up eye)
    "frame_02": (567, 293, 135, 67),   # auto clipped (cat)
    "frame_08": (1035, 275, 135, 70),  # hand (cat)
    "frame_12": (695, 220, 170, 80),   # hand (cat)
}


def main() -> int:
    fails = 0
    for frame, rect in MOUTH_BOX.items():
        for variant in ("half", "open"):
            base = K / f"{frame}.png"
            raw = MV / f"{frame}_{variant}.png"
            out = MV / f"{frame}_{variant}_locked_v1.png"
            ok = lock_one(base, raw, out, rect)
            print(("OK   " if ok else "FAIL ") + f"{frame}_{variant} rect={rect}")
            fails += 0 if ok else 1
    for frame, rect in EYE_BOX.items():
        base = K / f"{frame}.png"
        raw = EV / f"{frame}_closed.png"
        out = EV / f"{frame}_closed_locked_v1.png"
        ok = lock_one(base, raw, out, rect)
        print(("OK   " if ok else "FAIL ") + f"{frame}_closed rect={rect}")
        fails += 0 if ok else 1
    print(f"re-locked {len(MOUTH_BOX) * 2 + len(EYE_BOX) - fails} files")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
