#!/usr/bin/env python3
"""Create a provider-neutral sequential image plan."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


LOCK_CATEGORIES = ("characters", "wardrobe", "scene", "camera", "style", "props")
DEFAULT_PRESERVE = [
    "character identity",
    "wardrobe",
    "body proportions",
    "scene geometry",
    "lighting",
    "camera",
    "visual style",
    "screen direction",
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not slug:
        raise ValueError("sequence id must contain at least one letter or digit")
    return slug


def resolve_input_path(project: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    project_candidate = (project / candidate).resolve()
    if project_candidate.exists():
        return project_candidate
    return candidate.resolve()


def project_relative(project: Path, path: Path) -> str:
    try:
        return Path(os.path.relpath(path, project)).as_posix()
    except ValueError:
        return path.as_posix()


def portable_relative(path: Path, start: Path) -> str:
    try:
        return Path(os.path.relpath(path, start)).as_posix()
    except ValueError:
        return path.as_posix()


def action_phases(count: int) -> list[str]:
    presets = {
        1: ["key"],
        2: ["setup", "result"],
        3: ["setup", "action", "recovery"],
        4: ["setup", "anticipation", "action", "recovery"],
        5: ["setup", "anticipation", "action", "apex_or_contact", "recovery"],
    }
    if count in presets:
        return presets[count]
    phases = ["setup", "anticipation"]
    middle_count = max(0, count - 4)
    phases.extend(f"progression_{index + 1:02d}" for index in range(middle_count))
    phases.extend(["apex_or_contact", "recovery"])
    return phases[:count]


def parse_locks(values: list[str]) -> dict[str, list[str]]:
    locks = {category: [] for category in LOCK_CATEGORIES}
    for value in values:
        if "=" not in value:
            raise ValueError(f"lock must use category=value: {value!r}")
        category, fact = value.split("=", 1)
        category = category.strip()
        fact = fact.strip()
        if category not in locks:
            allowed = ", ".join(LOCK_CATEGORIES)
            raise ValueError(f"unknown lock category {category!r}; use one of: {allowed}")
        if not fact:
            raise ValueError(f"lock fact cannot be empty: {value!r}")
        locks[category].append(fact)
    return locks


def provider_config(name: str, model: str) -> dict:
    normalized = name.strip().lower()
    capabilities = {
        "referenceImages": None,
        "multiImageReference": None,
        "sequentialGroup": None,
        "acceptsRequestedCount": None,
        "guaranteesRequestedCount": None,
        "orderedSequentialOutputs": None,
        "imageEdit": None,
        "seed": None,
        "negativePrompt": None,
        "maskEdit": None,
    }
    options: dict[str, object] = {}
    if normalized in {"dashscope", "bailian", "aliyun-bailian"}:
        normalized = "dashscope"
        model = model or "wan2.7-image-pro"
        capabilities.update(
            {
                "referenceImages": True,
                "multiImageReference": True,
                "sequentialGroup": True,
                "acceptsRequestedCount": True,
                "guaranteesRequestedCount": False,
                "orderedSequentialOutputs": True,
                "imageEdit": True,
                "seed": False,
                "negativePrompt": False,
                "maskEdit": False,
            }
        )
        options = {"size": "2K", "watermark": False}
    return {
        "name": normalized or "generic",
        "model": model,
        "capabilities": capabilities,
        "options": options,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a continuity-first story image sequence plan."
    )
    parser.add_argument("project_dir", help="Project or episode directory.")
    parser.add_argument("--sequence-id", required=True)
    parser.add_argument("--reference", action="append", default=[], help="Identity reference.")
    parser.add_argument("--style-reference", action="append", default=[])
    parser.add_argument("--setting-reference", action="append", default=[])
    parser.add_argument(
        "--shot",
        action="append",
        required=True,
        help="Shot description in chronological order; repeat for every shot.",
    )
    parser.add_argument(
        "--lock",
        action="append",
        default=[],
        metavar="CATEGORY=FACT",
        help="Repeatable hard lock. Categories: " + ", ".join(LOCK_CATEGORIES),
    )
    parser.add_argument("--story", help="Optional story or storyboard source path.")
    parser.add_argument("--provider", default="generic")
    parser.add_argument("--model", default="")
    parser.add_argument("--aspect-ratio", default="16:9")
    parser.add_argument("--output-dir", help="Frame output directory relative to project.")
    parser.add_argument("--plan", help="Plan path; defaults under config/image_sequences.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project = Path(args.project_dir).expanduser().resolve()
    if not project.is_dir():
        parser.error(f"project directory does not exist: {project}")

    try:
        sequence_id = slugify(args.sequence_id)
        locks = parse_locks(args.lock)
    except ValueError as exc:
        parser.error(str(exc))

    plan_path = (
        resolve_input_path(project, args.plan)
        if args.plan
        else project / "config" / "image_sequences" / f"{sequence_id}.json"
    )
    if plan_path.exists() and not args.force:
        parser.error(f"plan already exists: {plan_path}; use --force to replace it")

    reference_groups: dict[str, list[str]] = {}
    for key, values in (
        ("identityReferences", args.reference),
        ("styleReferences", args.style_reference),
        ("settingReferences", args.setting_reference),
    ):
        paths = []
        for value in values:
            resolved = resolve_input_path(project, value)
            if not resolved.is_file():
                parser.error(f"reference does not exist: {resolved}")
            paths.append(project_relative(project, resolved))
        reference_groups[key] = paths

    story = None
    if args.story:
        story_path = resolve_input_path(project, args.story)
        if not story_path.is_file():
            parser.error(f"story source does not exist: {story_path}")
        story = project_relative(project, story_path)

    output_directory = args.output_dir or f"assets/images/{sequence_id}"
    phases = action_phases(len(args.shot))
    shots = []
    for index, (description, phase) in enumerate(zip(args.shot, phases), start=1):
        shots.append(
            {
                "id": f"shot_{index:02d}",
                "order": index,
                "actionPhase": phase,
                "description": description.strip(),
                "stateBefore": {},
                "stateAfter": {},
                "allowedChanges": [
                    "pose",
                    "expression",
                    "gaze",
                    "moving prop position",
                    "secondary motion",
                ],
                "preserve": list(DEFAULT_PRESERVE),
                "referenceFrame": None,
                "status": "planned",
                "output": None,
                "review": {"issues": [], "notes": ""},
            }
        )

    project_root_from_plan = portable_relative(project, plan_path.parent)
    plan = {
        "schemaVersion": 2,
        "sequenceId": sequence_id,
        "source": {"story": story, "notes": ""},
        "paths": {
            "projectRoot": project_root_from_plan,
            "outputDirectory": Path(output_directory).as_posix(),
        },
        "output": {"aspectRatio": args.aspect_ratio},
        "provider": provider_config(args.provider, args.model),
        "continuity": {
            **reference_groups,
            "allowTextOnly": False,
            "hardLocks": locks,
            "negativeConstraints": [
                "different character identity",
                "face drift",
                "wardrobe changes",
                "extra characters",
                "extra limbs or fingers",
                "duplicate moving props",
                "unplanned camera or background changes",
                "text or watermark",
            ],
            "grouping": {
                "preferSequentialGroup": True,
                "maxShotsPerGroup": 5,
                "overlapShots": 1,
            },
        },
        "shots": shots,
        "candidates": [],
        "runs": [],
    }

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(plan_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
