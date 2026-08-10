#!/usr/bin/env python3
"""Run a batch of episode image generations through gen_image.py (serial).

Replaces the per-day `gen_*.sh` codex scripts. The batch file is plain JSON so
the full shot list + prompts stay in version control next to the episode.

Batch file format:

{
  "defaults": {
    "model": "wan2.7-image-pro",        // optional
    "size": "2K",                        // optional
    "refs": ["assets/style_master.png"], // optional, prepended to every shot
    "promptSuffix": "Style lock: ... Avoid: ..."  // appended to every prompt
  },
  "shots": [
    {
      "name": "frame_00",
      "out": "assets/keyframes/frame_00.png",
      "prompt": "Use case: establishing shot ...",   // or "promptFile": "p/frame_00.txt"
      "refs": ["assets/scene_room.png"],             // optional, appended after defaults.refs
      "size": "2K"                                    // optional per-shot override
    }
  ]
}

Relative paths resolve against the batch file's directory. Existing outputs are
skipped unless --overwrite is given. Serial execution on purpose: review each
frame before it becomes the reference of the next run.

Usage:
  python gen_batch.py tools/gen_day2_seg1.json [--only frame_00,frame_01] [--overwrite]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GEN_IMAGE = SCRIPT_DIR / "gen_image.py"


def load_batch(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("shots"), list):
        raise ValueError(f"batch file must be an object with a shots array: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("batch", help="batch JSON file")
    parser.add_argument("--only", help="comma-separated shot names to run")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    batch_path = Path(args.batch).resolve()
    try:
        batch = load_batch(batch_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    base = batch_path.parent
    defaults = batch.get("defaults") or {}
    only = set(args.only.split(",")) if args.only else None

    shots = []
    for shot in batch["shots"]:
        name = shot.get("name")
        if not name or not shot.get("out"):
            parser.error(f"every shot needs name and out: {json.dumps(shot, ensure_ascii=False)}")
        if only and name not in only:
            continue
        if not shot.get("prompt") and not shot.get("promptFile"):
            parser.error(f"{name}: needs prompt or promptFile")
        shots.append(shot)

    ok, missing = [], []
    for index, shot in enumerate(shots, start=1):
        name = shot["name"]
        out = (base / shot["out"]).resolve()
        print(f"== [{index}/{len(shots)}] {name} -> {out}", flush=True)

        argv = [sys.executable, str(GEN_IMAGE), "--out", str(out)]
        if shot.get("promptFile"):
            argv += ["--prompt-file", str((base / shot["promptFile"]).resolve())]
        else:
            prompt = shot["prompt"].strip()
            suffix = (defaults.get("promptSuffix") or "").strip()
            argv += ["--prompt", f"{prompt}\n{suffix}" if suffix else prompt]
        for ref in list(defaults.get("refs") or []) + list(shot.get("refs") or []):
            argv += ["--ref", str((base / ref).resolve())]
        argv += ["--model", shot.get("model") or defaults.get("model") or "wan2.7-image-pro"]
        argv += ["--size", str(shot.get("size") or defaults.get("size") or "2K")]
        if shot.get("n") or defaults.get("n"):
            argv += ["--n", str(shot.get("n") or defaults.get("n"))]
        if args.overwrite:
            argv.append("--overwrite")

        result = subprocess.run(argv, capture_output=True, text=True)
        for line in (result.stdout + result.stderr).splitlines():
            print(f"   {line}", flush=True)
        if result.returncode == 0 and out.is_file():
            ok.append(name)
        else:
            missing.append(name)
            print(f"== MISSING {name}", flush=True)

    print(f"== batch done: {len(ok)} ok, {len(missing)} missing", flush=True)
    if missing:
        print("missing: " + ", ".join(missing), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
