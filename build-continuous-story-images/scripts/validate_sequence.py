#!/usr/bin/env python3
"""Validate a sequential image plan before generation or final delivery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VALID_STATUSES = {"planned", "generated", "accepted", "needs_repair", "rejected"}
VALID_CANDIDATE_STATUSES = {"unassigned", "assigned", "rejected"}
REFERENCE_KEYS = ("identityReferences", "styleReferences", "settingReferences")


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value must be an object")
    return data


def resolve_project_root(plan_path: Path, plan: dict) -> Path:
    value = plan.get("paths", {}).get("projectRoot", ".")
    return (plan_path.parent / value).resolve()


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    parser.add_argument("--final", action="store_true", help="Require approved existing outputs.")
    args = parser.parse_args()

    plan_path = Path(args.plan).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    try:
        plan = load_json(plan_path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    if plan.get("schemaVersion") != 2:
        errors.append("schemaVersion must be 2")
    if not isinstance(plan.get("sequenceId"), str) or not plan["sequenceId"].strip():
        errors.append("sequenceId must be a non-empty string")

    paths = plan.get("paths")
    if not isinstance(paths, dict):
        errors.append("paths must be an object")
        paths = {}
    if not isinstance(paths.get("outputDirectory"), str) or not paths.get("outputDirectory"):
        errors.append("paths.outputDirectory must be a non-empty string")

    project_root = resolve_project_root(plan_path, plan)
    if not project_root.is_dir():
        errors.append(f"resolved project root does not exist: {project_root}")

    provider = plan.get("provider")
    if not isinstance(provider, dict):
        errors.append("provider must be an object")
        provider = {}
    if not isinstance(provider.get("name"), str) or not provider.get("name"):
        errors.append("provider.name must be a non-empty string")
    capabilities = provider.get("capabilities")
    if not isinstance(capabilities, dict):
        errors.append("provider.capabilities must be an object")
        capabilities = {}
    if (
        capabilities.get("guaranteesRequestedCount") is True
        and capabilities.get("acceptsRequestedCount") is not True
    ):
        warnings.append(
            "provider guaranteesRequestedCount=true without acceptsRequestedCount=true"
        )
    if (
        capabilities.get("orderedSequentialOutputs") is True
        and capabilities.get("sequentialGroup") is not True
    ):
        warnings.append(
            "provider orderedSequentialOutputs=true without sequentialGroup=true"
        )

    continuity = plan.get("continuity")
    if not isinstance(continuity, dict):
        errors.append("continuity must be an object")
        continuity = {}

    reference_count = 0
    for key in REFERENCE_KEYS:
        values = continuity.get(key, [])
        if not isinstance(values, list):
            errors.append(f"continuity.{key} must be an array")
            continue
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value:
                errors.append(f"continuity.{key}[{index}] must be a non-empty path")
                continue
            reference_count += 1
            resolved = resolve_project_path(project_root, value)
            if not resolved.is_file():
                errors.append(f"missing {key} file: {resolved}")

    allow_text_only = continuity.get("allowTextOnly") is True
    if not continuity.get("identityReferences") and not allow_text_only:
        warnings.append(
            "no identity reference; add one or explicitly set continuity.allowTextOnly=true"
        )
    if reference_count and capabilities.get("referenceImages") is False:
        warnings.append("provider declares referenceImages=false but the plan contains references")

    locks = continuity.get("hardLocks")
    if not isinstance(locks, dict):
        errors.append("continuity.hardLocks must be an object")
        locks = {}
    lock_count = 0
    for category, values in locks.items():
        if not isinstance(values, list):
            errors.append(f"continuity.hardLocks.{category} must be an array")
            continue
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f"continuity.hardLocks.{category}[{index}] must be a non-empty string"
                )
            else:
                lock_count += 1
    if lock_count == 0:
        warnings.append("hardLocks is empty; identity and scene continuity are underspecified")

    negatives = continuity.get("negativeConstraints")
    if not isinstance(negatives, list) or not negatives:
        warnings.append("negativeConstraints is empty")

    grouping = continuity.get("grouping")
    if not isinstance(grouping, dict):
        errors.append("continuity.grouping must be an object")
        grouping = {}
    max_group = grouping.get("maxShotsPerGroup")
    if not isinstance(max_group, int) or max_group < 1:
        errors.append("continuity.grouping.maxShotsPerGroup must be a positive integer")
        max_group = 0
    overlap = grouping.get("overlapShots")
    if not isinstance(overlap, int) or overlap < 0:
        errors.append("continuity.grouping.overlapShots must be a non-negative integer")

    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("shots must be a non-empty array")
        shots = []

    ids: set[str] = set()
    outputs: set[str] = set()
    expected_orders = list(range(1, len(shots) + 1))
    actual_orders = []
    output_status: dict[str, str] = {}
    previous = None
    for index, shot in enumerate(shots):
        prefix = f"shots[{index}]"
        if not isinstance(shot, dict):
            errors.append(f"{prefix} must be an object")
            continue
        shot_id = shot.get("id")
        if not isinstance(shot_id, str) or not shot_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif shot_id in ids:
            errors.append(f"duplicate shot id: {shot_id}")
        else:
            ids.add(shot_id)
        actual_orders.append(shot.get("order"))
        if not isinstance(shot.get("actionPhase"), str) or not shot["actionPhase"].strip():
            errors.append(f"{prefix}.actionPhase must be a non-empty string")
        if not isinstance(shot.get("description"), str) or not shot["description"].strip():
            errors.append(f"{prefix}.description must be a non-empty string")
        for key in ("stateBefore", "stateAfter", "review"):
            if not isinstance(shot.get(key), dict):
                errors.append(f"{prefix}.{key} must be an object")
        for key in ("allowedChanges", "preserve"):
            values = shot.get(key)
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                errors.append(f"{prefix}.{key} must be an array of non-empty strings")
        status = shot.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"{prefix}.status must be one of: {', '.join(sorted(VALID_STATUSES))}")
        output = shot.get("output")
        if output is not None and (not isinstance(output, str) or not output):
            errors.append(f"{prefix}.output must be null or a non-empty path")
        elif output:
            if output in outputs:
                errors.append(f"duplicate shot output path: {output}")
            outputs.add(output)
            output_status[output] = status

        reference_frame = shot.get("referenceFrame")
        if reference_frame is not None and (
            not isinstance(reference_frame, str) or not reference_frame
        ):
            errors.append(f"{prefix}.referenceFrame must be null or a non-empty path")

        if previous and isinstance(previous, dict):
            after = previous.get("stateAfter")
            before = shot.get("stateBefore")
            if isinstance(after, dict) and isinstance(before, dict):
                for key in sorted(set(after) & set(before)):
                    if after[key] != before[key]:
                        warnings.append(
                            f"{prefix}.stateBefore.{key} conflicts with prior stateAfter: "
                            f"{before[key]!r} != {after[key]!r}"
                        )
        previous = shot

        if args.final:
            if status != "accepted":
                errors.append(f"{prefix} is not accepted")
            if not output:
                errors.append(f"{prefix} has no output")
            elif not resolve_project_path(project_root, output).is_file():
                errors.append(f"{prefix} output does not exist: {output}")

    if actual_orders != expected_orders:
        errors.append(f"shot order must be consecutive {expected_orders}, got {actual_orders}")
    if max_group and len(shots) > max_group and grouping.get("overlapShots", 0) < 1:
        warnings.append("long sequence exceeds maxShotsPerGroup without an overlap anchor")
    if len(shots) > 1 and capabilities.get("sequentialGroup") is not True:
        infos.append("provider has no confirmed sequentialGroup capability; use reviewed-frame fallback")
    elif (
        len(shots) > 1
        and capabilities.get("orderedSequentialOutputs") is not True
    ):
        infos.append(
            "provider output order is not confirmed; register candidates and assign by visual review"
        )

    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        reference_frame = shot.get("referenceFrame")
        if reference_frame and output_status.get(reference_frame) == "rejected":
            errors.append(f"shots[{index}] inherits from a rejected output: {reference_frame}")

    candidates = plan.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates must be an array")
        candidates = []
    candidate_paths: set[str] = set()
    shot_by_id = {
        shot.get("id"): shot for shot in shots if isinstance(shot, dict)
    }
    for index, candidate in enumerate(candidates):
        prefix = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix} must be an object")
            continue
        path = candidate.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"{prefix}.path must be a non-empty path")
            continue
        if path in candidate_paths:
            errors.append(f"duplicate candidate path: {path}")
        candidate_paths.add(path)
        if not resolve_project_path(project_root, path).is_file():
            errors.append(f"{prefix} file does not exist: {path}")
        status = candidate.get("status")
        if status not in VALID_CANDIDATE_STATUSES:
            errors.append(
                f"{prefix}.status must be one of: "
                + ", ".join(sorted(VALID_CANDIDATE_STATUSES))
            )
        assigned_shot_id = candidate.get("assignedShotId")
        if status == "assigned":
            assigned_shot = shot_by_id.get(assigned_shot_id)
            if assigned_shot is None:
                errors.append(f"{prefix} references unknown assignedShotId")
            elif assigned_shot.get("output") != path:
                errors.append(
                    f"{prefix} is assigned to {assigned_shot_id} but its output differs"
                )
        elif assigned_shot_id is not None:
            errors.append(f"{prefix}.assignedShotId must be null unless status=assigned")
        if not isinstance(candidate.get("sourceRunId"), str) or not candidate.get(
            "sourceRunId"
        ):
            errors.append(f"{prefix}.sourceRunId must be a non-empty string")
    if args.final:
        unassigned_count = sum(
            1 for candidate in candidates if candidate.get("status") == "unassigned"
        )
        if unassigned_count:
            infos.append(
                f"{unassigned_count} surplus candidate(s) remain unassigned; "
                "they do not block final delivery"
            )

    runs = plan.get("runs")
    if not isinstance(runs, list):
        errors.append("runs must be an array")
        runs = []
    for index, run in enumerate(runs):
        prefix = f"runs[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{prefix} must be an object")
            continue
        requested_count = run.get("requestedCount")
        returned_count = run.get("returnedCount")
        if requested_count is not None and (
            not isinstance(requested_count, int) or requested_count < 1
        ):
            errors.append(f"{prefix}.requestedCount must be null or a positive integer")
        if returned_count is not None and (
            not isinstance(returned_count, int) or returned_count < 0
        ):
            errors.append(
                f"{prefix}.returnedCount must be null or a non-negative integer"
            )

    for message in infos:
        print(f"INFO: {message}")
    for message in warnings:
        print(f"WARNING: {message}")
    for message in errors:
        print(f"ERROR: {message}")

    if errors or (args.strict and warnings):
        print(
            f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s), "
            f"{len(infos)} info message(s)"
        )
        return 1
    print(
        f"OK: {len(shots)} shot(s), {reference_count} reference(s), "
        f"{lock_count} hard lock(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
