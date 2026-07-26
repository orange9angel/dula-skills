#!/usr/bin/env python3
"""Record an explicit human or vision review decision for one sequence shot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


VALID_STATUSES = ("generated", "accepted", "needs_repair", "rejected")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("sequence plan must be a JSON object")
    return data


def write_json_atomic(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def portable_project_path(project_root: Path, value: str) -> str:
    resolved = resolve_project_path(project_root, value)
    try:
        return Path(os.path.relpath(resolved, project_root)).as_posix()
    except ValueError:
        return resolved.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--shot", required=True, help="Shot id.")
    parser.add_argument("--status", required=True, choices=VALID_STATUSES)
    parser.add_argument("--output", help="Generated image path.")
    parser.add_argument("--reference-frame", help="Approved continuity frame path.")
    parser.add_argument("--issue", action="append", default=[])
    parser.add_argument("--clear-issues", action="store_true")
    parser.add_argument("--notes")
    args = parser.parse_args()

    plan_path = Path(args.plan).expanduser().resolve()
    try:
        plan = load_json(plan_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    project_root = (
        plan_path.parent / plan.get("paths", {}).get("projectRoot", ".")
    ).resolve()
    shots = {shot.get("id"): shot for shot in plan.get("shots", []) if isinstance(shot, dict)}
    if args.shot not in shots:
        parser.error(f"unknown shot id: {args.shot}")
    shot = shots[args.shot]

    if args.output:
        output = portable_project_path(project_root, args.output)
        if not resolve_project_path(project_root, output).is_file():
            parser.error(f"output does not exist: {args.output}")
        for candidate in plan.get("candidates", []):
            if candidate.get("path") != output:
                continue
            assigned_shot = candidate.get("assignedShotId")
            if assigned_shot and assigned_shot != args.shot:
                parser.error(
                    f"candidate is already assigned to another shot: {assigned_shot}"
                )
            candidate["status"] = (
                "rejected" if args.status == "rejected" else "assigned"
            )
            candidate["assignedShotId"] = (
                None if args.status == "rejected" else args.shot
            )
        shot["output"] = output
    if args.status == "accepted":
        output = shot.get("output")
        if not output:
            parser.error("accepted status requires an output")
        if not resolve_project_path(project_root, output).is_file():
            parser.error(f"accepted output does not exist: {output}")

    if args.reference_frame:
        reference = portable_project_path(project_root, args.reference_frame)
        if not resolve_project_path(project_root, reference).is_file():
            parser.error(f"reference frame does not exist: {args.reference_frame}")
        accepted_outputs = {
            item.get("output")
            for item in plan.get("shots", [])
            if item.get("status") == "accepted" and item.get("output")
        }
        if reference not in accepted_outputs:
            parser.error("reference frame must be the output of an accepted shot")
        shot["referenceFrame"] = reference

    review = shot.setdefault("review", {"issues": [], "notes": ""})
    if args.clear_issues:
        review["issues"] = []
    if args.issue:
        review.setdefault("issues", []).extend(args.issue)
    if args.notes is not None:
        review["notes"] = args.notes
    if args.status == "accepted" and review.get("issues"):
        parser.error("accepted shot cannot retain review issues; use --clear-issues")

    shot["status"] = args.status
    write_json_atomic(plan_path, plan)
    print(f"{args.shot}: {args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
