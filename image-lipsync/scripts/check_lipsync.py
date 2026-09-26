#!/usr/bin/env python3
"""Validate the episode's raster mouth rigs, cue cells, and visual timeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


VALID_STATES = {"closed", "half", "open"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def asset_path(episode: Path, value: str, default_folder: str = "keyframes") -> Path:
    normalized = value.replace("\\", "/").lstrip("/")
    if ".." in normalized:
        raise ValueError(f"Unsafe asset path: {value}")
    if "/" not in normalized:
        normalized = f"{default_folder}/{normalized}"
    return episode / "assets" / normalized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_dir", nargs="?", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--syllable-exempt",
        action="append",
        default=[],
        metavar="CHARACTER",
        help="character whose cue entries may legitimately have no syllable "
             "sequence (e.g. non-verbal SFX-voiced characters); repeatable",
    )
    parser.add_argument(
        "--act-boundary",
        action="append",
        default=[],
        type=float,
        metavar="SECONDS",
        help="timeline act boundary for the cadence summary print; repeatable",
    )
    args = parser.parse_args()
    episode = args.episode_dir.resolve()
    timeline = load_json(episode / "config" / "keyframe_timeline.json")
    rigs = load_json(episode / "config" / "mouth_rigs.json").get("rigs", {})
    cues = load_json(episode / "config" / "lipsync_cues.json")
    cue_entries = {int(item["index"]): item for item in cues.get("entries", [])}
    errors: list[str] = []

    frames = timeline.get("frames", [])
    times = [float(frame["at"]) for frame in frames]
    if not times or times[0] != 0 or any(right <= left for left, right in zip(times, times[1:])):
        errors.append("Timeline must start at zero and be strictly increasing")

    image_size_cache: dict[Path, tuple[int, int]] = {}

    def image_size(path: Path) -> tuple[int, int] | None:
        if path in image_size_cache:
            return image_size_cache[path]
        if not path.exists():
            errors.append(f"Missing image: {path.relative_to(episode)}")
            return None
        with Image.open(path) as image:
            image_size_cache[path] = image.size
        return image_size_cache[path]

    used_rigs: set[str] = set()
    for frame in frames:
        base_path = asset_path(episode, frame["file"])
        base_size = image_size(base_path)
        rig_id = frame.get("mouthRig")
        if not rig_id:
            continue
        used_rigs.add(rig_id)
        rig = rigs.get(rig_id)
        if not rig:
            errors.append(f"Timeline references unknown mouth rig: {rig_id}")
            continue
        raw_entry = rig.get("entry", -1)
        for entry in (raw_entry if isinstance(raw_entry, list) else [int(raw_entry)]):
            if int(entry) not in cue_entries:
                errors.append(f"Mouth rig {rig_id} references missing cue entry {entry}")
        if rig.get("mode") == "procedural":
            anchor = rig.get("anchor", [])
            size = rig.get("size", [])
            if len(anchor) != 2 or len(size) != 2:
                errors.append(f"Procedural mouth rig {rig_id} has invalid anchor/size")
            continue

        rect = rig.get("rect", [])
        if len(rect) != 4:
            errors.append(f"Mouth rig {rig_id} has invalid rect")
            continue
        if base_size:
            x, y, width, height = map(int, rect)
            if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > base_size[0] or y + height > base_size[1]:
                errors.append(f"Mouth rig {rig_id} rect {rect} exceeds base size {base_size}")
        for state in VALID_STATES:
            value = rig.get("variants", {}).get(state)
            if not value:
                errors.append(f"Mouth rig {rig_id} is missing {state} variant")
                continue
            variant_size = image_size(asset_path(episode, value, "mouth_variants"))
            if base_size and variant_size and variant_size != base_size:
                errors.append(
                    f"Mouth rig {rig_id} {state} size {variant_size} != base {base_size}"
                )

    for rig_id in rigs:
        if rig_id not in used_rigs:
            errors.append(f"Unused mouth rig: {rig_id}")

    mouth_fps = float(cues.get("mouthFrameRate", 0))
    if mouth_fps <= 0:
        errors.append("mouthFrameRate must be positive")
    for index, cue in cue_entries.items():
        cells = cue.get("cells", [])
        if not cells:
            errors.append(f"Cue entry {index} has no mouth cells")
            continue
        alignment = cue.get("alignment")
        if alignment not in ("energy-gated-text-viseme-v1", "energy-gated-sfx-v1", "placeholder-pre-audio-v1"):
            errors.append(f"Cue entry {index} has unknown alignment {alignment!r}")
        if alignment == "placeholder-pre-audio-v1":
            print(f"WARN: cue entry {index} is a pre-audio placeholder; regenerate with build_lipsync.py")
        if alignment in ("energy-gated-text-viseme-v1", "placeholder-pre-audio-v1") and cue.get("character") not in args.syllable_exempt and not cue.get("syllables"):
            errors.append(f"Cue entry {index} has no Chinese syllable sequence")
        energy_cells = cue.get("energyCells", [])
        if len(energy_cells) != len(cells):
            errors.append(
                f"Cue entry {index} energy/viseme length mismatch: "
                f"{len(energy_cells)} != {len(cells)}"
            )
        invalid = sorted(set(cells) - VALID_STATES)
        if invalid:
            errors.append(f"Cue entry {index} contains invalid states: {invalid}")
        expected = max(1, round(float(cue["effectiveDuration"]) * mouth_fps))
        if abs(len(cells) - expected) > 1:
            errors.append(f"Cue entry {index} has {len(cells)} cells; expected about {expected}")

    print(
        f"Checked {len(frames)} timeline beats, {len(rigs)} mouth rigs, "
        f"{len(cue_entries)} audio cues, {len(image_size_cache)} images."
    )
    if args.act_boundary:
        bounds = [0.0, *sorted(args.act_boundary), float("inf")]
        counts = [
            sum(1 for time in times if low <= time < high)
            for low, high in zip(bounds, bounds[1:])
        ]
        cadence = ", ".join(f"seg{i + 1} poses={count}" for i, count in enumerate(counts))
        print(f"Act cadence: {cadence}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Lip-sync and visual timeline checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
