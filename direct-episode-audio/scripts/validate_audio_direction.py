#!/usr/bin/env python3
"""Validate a Dula audio direction plan against its episode sources."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from init_audio_direction import parse_story, sha256


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, abs_tol=0.002)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--warnings-as-errors", action="store_true")
    args = parser.parse_args()
    episode = args.episode.resolve()
    plan_path = args.plan.resolve() if args.plan else episode / "config" / "audio_direction.json"
    plan = load_json(plan_path)
    errors: list[str] = []
    warnings: list[str] = []

    if plan.get("version") != 1:
        errors.append("version must be 1")
    if plan.get("status") not in {"draft", "reviewed"}:
        errors.append("status must be draft or reviewed")
    elif plan.get("status") == "draft":
        warnings.append("plan is still draft; perform the contextual director pass")

    for source in plan.get("sources", []):
        relative = Path(str(source.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"unsafe source path: {relative}")
            continue
        path = episode / relative
        if not path.exists():
            errors.append(f"missing source: {relative}")
        elif source.get("sha256") != sha256(path):
            errors.append(f"stale source hash: {relative}")

    story_entries = parse_story(episode / "script.story")
    spoken = {
        int(entry["index"]): entry
        for entry in story_entries
        if entry["character"] and entry["dialogue"]
    }
    directed: dict[int, dict[str, Any]] = {}
    for item in plan.get("dialogue", []):
        try:
            index = int(item["entry"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"dialogue item has invalid entry: {item!r}")
            continue
        if index in directed:
            errors.append(f"duplicate dialogue entry: {index}")
        directed[index] = item
        source = spoken.get(index)
        if not source:
            errors.append(f"dialogue entry {index} does not exist in script.story")
            continue
        if item.get("character") != source["character"]:
            errors.append(f"dialogue entry {index} character does not match script.story")
        if "".join(str(item.get("text", "")).split()) != "".join(source["dialogue"].split()):
            errors.append(f"dialogue entry {index} text does not match script.story")
        if not close(float(item.get("startTime", -1)), float(source["startTime"])):
            errors.append(f"dialogue entry {index} startTime is stale")
        if not close(float(item.get("endTime", -1)), float(source["endTime"])):
            errors.append(f"dialogue entry {index} endTime is stale")
        if not str(item.get("intent", "")).strip():
            warnings.append(f"dialogue entry {index} has no intent")
        if not str(item.get("subtext", "")).strip():
            warnings.append(f"dialogue entry {index} has no reviewed subtext")
        delivery = item.get("delivery", {})
        for field in ("energy", "pace", "volume", "pitchSemitones"):
            if field not in delivery:
                errors.append(f"dialogue entry {index} delivery is missing {field}")
        if not 0 <= float(delivery.get("energy", -1)) <= 1:
            errors.append(f"dialogue entry {index} energy must be between 0 and 1")
        pace = float(delivery.get("pace", 0))
        volume = float(delivery.get("volume", 0))
        pitch = float(delivery.get("pitchSemitones", 99))
        if not 0.75 <= pace <= 1.25:
            errors.append(f"dialogue entry {index} pace is unsafe: {pace}")
        elif not 0.90 <= pace <= 1.10:
            warnings.append(f"dialogue entry {index} pace is unusually strong: {pace}")
        if not 0.5 <= volume <= 1.5:
            errors.append(f"dialogue entry {index} volume is unsafe: {volume}")
        elif not 0.85 <= volume <= 1.12:
            warnings.append(f"dialogue entry {index} volume is unusually strong: {volume}")
        if not -2 <= pitch <= 2:
            errors.append(f"dialogue entry {index} pitch shift is unsafe: {pitch}st")
        elif abs(pitch) > 0.5:
            warnings.append(f"dialogue entry {index} pitch shift may alter voice identity: {pitch}st")

    missing = sorted(set(spoken) - set(directed))
    extra = sorted(set(directed) - set(spoken))
    if missing:
        errors.append(f"missing spoken entries: {missing}")
    if extra:
        errors.append(f"unknown directed entries: {extra}")

    timeline_path = episode / "config" / "keyframe_timeline.json"
    known_shots: set[str] = set()
    if timeline_path.exists():
        timeline = load_json(timeline_path)
        known_shots = {
            str(frame["shot"])
            for frame in timeline.get("frames", [])
            if frame.get("shot")
        }
    for item in plan.get("dialogue", []) + plan.get("ambience", []) + plan.get("sfx", []):
        for shot in item.get("shotIds", []):
            if known_shots and shot not in known_shots:
                errors.append(f"unknown shot anchor {shot!r} in {item.get('id', item.get('entry'))}")

    story_end = max((float(entry["endTime"]) for entry in story_entries), default=0.0)
    identifiers: set[str] = set()
    for section in ("ambience", "sfx", "music", "exclusions"):
        values = plan.get(section, [])
        if not isinstance(values, list):
            errors.append(f"{section} must be an array")
            continue
        for item in values:
            identifier = str(item.get("id", "")).strip()
            if not identifier:
                errors.append(f"{section} item has no id")
            elif identifier in identifiers:
                errors.append(f"duplicate audio id: {identifier}")
            identifiers.add(identifier)
            if section == "exclusions":
                if not str(item.get("reason", "")).strip():
                    errors.append(f"exclusion {identifier} has no reason")
                continue
            start = float(item.get("startTime", -1))
            end = float(item.get("endTime", start))
            if start < 0 or start > story_end + 0.1:
                errors.append(f"{section} {identifier} has invalid startTime: {start}")
            if end < start or end > story_end + 0.1:
                errors.append(f"{section} {identifier} has invalid endTime: {end}")

    policies = plan.get("policies", {})
    if policies.get("priority") != ["dialogue", "storySfx", "ambience", "music"]:
        errors.append("mix priority must be dialogue > storySfx > ambience > music")
    if policies.get("musicMode") not in {"directed", "auto", "none"}:
        errors.append("musicMode must be directed, auto, or none")
    if policies.get("musicMode") == "directed" and not plan.get("music"):
        warnings.append("musicMode is directed but there are no music cues")
    if policies.get("musicMode") == "none" and plan.get("music"):
        errors.append("musicMode none conflicts with non-empty music cues")

    raw = plan_path.read_text(encoding="utf-8")
    if "TODO" in raw:
        errors.append("plan contains unresolved TODO markers")

    print(
        f"Checked {len(directed)} dialogue directions, {len(plan.get('ambience', []))} ambience, "
        f"{len(plan.get('sfx', []))} SFX, {len(plan.get('music', []))} music cues."
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors or (warnings and args.warnings_as_errors):
        return 1
    print("Audio direction validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
