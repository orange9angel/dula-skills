#!/usr/bin/env python3
"""Compile a sequence plan into provider-neutral group and fallback requests."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


REFERENCE_KEYS = (
    ("identity", "identityReferences"),
    ("style", "styleReferences"),
    ("setting", "settingReferences"),
)


def load_plan(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("sequence plan must be a JSON object")
    return data


def portable_relative(path: Path, start: Path) -> str:
    try:
        return Path(os.path.relpath(path, start)).as_posix()
    except ValueError:
        return path.as_posix()


def list_lines(title: str, values: list[str]) -> list[str]:
    if not values:
        return []
    return [f"{title}:"] + [f"- {value}" for value in values]


def lock_lines(locks: dict) -> list[str]:
    lines = ["HARD CONTINUITY LOCKS — preserve these in every frame:"]
    for category, values in locks.items():
        if values:
            lines.append(f"{category}:")
            lines.extend(f"- {value}" for value in values)
    return lines


def state_text(label: str, state: dict) -> list[str]:
    if not state:
        return []
    return [f"{label}: " + "; ".join(f"{key}={value}" for key, value in state.items())]


def group_prompt(plan: dict) -> str:
    continuity = plan["continuity"]
    shots = plan["shots"]
    lines = [
        f"Aim to create one ordered sequential story-image group with one image for each of these {len(shots)} narrative shots.",
        "Preserve the numbered action order even if the active tool controls the actual return count.",
        "Treat the frames as neighboring moments of one continuous action, not unrelated variants.",
        "Keep the same character identity, scene state, visual style, camera setup, lighting, scale, and screen direction unless a shot explicitly allows a change.",
        "",
        *lock_lines(continuity.get("hardLocks", {})),
        "",
        "ORDERED ACTION FRAMES:",
    ]
    for shot in shots:
        lines.append(
            f"{shot['order']}. [{shot['id']} | {shot['actionPhase']}] {shot['description']}"
        )
        lines.extend(state_text("   state before", shot.get("stateBefore", {})))
        lines.extend(state_text("   state after", shot.get("stateAfter", {})))
        allowed = ", ".join(shot.get("allowedChanges", []))
        if allowed:
            lines.append(f"   change only: {allowed}")
    negatives = continuity.get("negativeConstraints", [])
    if negatives:
        lines.extend(["", *list_lines("AVOID", negatives)])
    return "\n".join(lines).strip()


def fallback_prompt(plan: dict, shot: dict) -> str:
    continuity = plan["continuity"]
    lines = [
        f"Create only {shot['id']}, action phase {shot['actionPhase']}, as part of the same continuous sequence.",
        shot["description"],
        "Use the canonical references for identity and the approved continuity frame for immediate temporal state when supplied.",
        "Do not redesign the character, wardrobe, scene, camera, lighting, or visual style.",
        "",
        *lock_lines(continuity.get("hardLocks", {})),
    ]
    lines.extend(state_text("STATE BEFORE", shot.get("stateBefore", {})))
    lines.extend(state_text("STATE AFTER", shot.get("stateAfter", {})))
    allowed = shot.get("allowedChanges", [])
    preserve = shot.get("preserve", [])
    lines.extend(list_lines("CHANGE ONLY", allowed))
    lines.extend(list_lines("PRESERVE", preserve))
    negatives = continuity.get("negativeConstraints", [])
    if negatives:
        lines.extend(list_lines("AVOID", negatives))
    return "\n".join(lines).strip()


def nearest_accepted_output(shots: list[dict], index: int) -> str | None:
    explicit = shots[index].get("referenceFrame")
    if explicit:
        return explicit
    for prior in reversed(shots[:index]):
        if prior.get("status") == "accepted" and prior.get("output"):
            return prior["output"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--output", help="Output request JSON path.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    plan_path = Path(args.plan).expanduser().resolve()
    try:
        plan = load_plan(plan_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else plan_path.with_name(plan_path.stem + ".generation.json")
    )
    if output_path.exists() and not args.force:
        parser.error(f"output exists: {output_path}; use --force to replace it")

    paths = plan.get("paths", {})
    project_root = (plan_path.parent / paths.get("projectRoot", ".")).resolve()
    references = []
    for role, key in REFERENCE_KEYS:
        for path in plan.get("continuity", {}).get(key, []):
            references.append({"role": role, "path": path})

    shots = []
    output_directory = paths.get("outputDirectory", f"assets/images/{plan['sequenceId']}")
    for index, shot in enumerate(plan["shots"]):
        output = shot.get("output") or (
            Path(output_directory) / f"{shot['id']}.png"
        ).as_posix()
        shots.append(
            {
                "id": shot["id"],
                "order": shot["order"],
                "actionPhase": shot["actionPhase"],
                "prompt": fallback_prompt(plan, shot),
                "continuityReference": nearest_accepted_output(plan["shots"], index),
                "output": output,
            }
        )

    capabilities = plan.get("provider", {}).get("capabilities", {})
    desired_count = len(plan["shots"])
    requested_count = (
        desired_count if capabilities.get("acceptsRequestedCount") is True else None
    )
    ordered_outputs = capabilities.get("orderedSequentialOutputs") is True
    guaranteed_count = capabilities.get("guaranteesRequestedCount") is True

    request = {
        "schemaVersion": 2,
        "sequenceId": plan["sequenceId"],
        "sequencePlan": portable_relative(plan_path, output_path.parent),
        "projectRoot": portable_relative(project_root, output_path.parent),
        "provider": plan["provider"],
        "strategy": {
            "mode": "group-first",
            "preferSequentialGroup": plan["continuity"]["grouping"].get(
                "preferSequentialGroup", True
            ),
            "maxShotsPerGroup": plan["continuity"]["grouping"].get(
                "maxShotsPerGroup", 5
            ),
            "overlapShots": plan["continuity"]["grouping"].get("overlapShots", 1),
            "fallbackRequiresApprovedContinuityFrame": True,
        },
        "aspectRatio": plan.get("output", {}).get("aspectRatio", "16:9"),
        "references": references,
        "negativeConstraints": plan["continuity"].get("negativeConstraints", []),
        "candidateDirectory": (
            Path(output_directory) / "_candidates"
        ).as_posix(),
        "group": {
            "prompt": group_prompt(plan),
            "shotIds": [shot["id"] for shot in plan["shots"]],
            "desiredCount": desired_count,
            "requestedCount": requested_count,
        },
        "resultPolicy": {
            "countIsAdvisory": not guaranteed_count,
            "orderIsAdvisory": not ordered_outputs,
            "assignmentMode": "position" if ordered_outputs else "visual-review",
            "onShortfall": "assign valid returns, then generate only unfilled shots",
            "onSurplus": "retain extras as unassigned candidates",
        },
        "shots": shots,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
