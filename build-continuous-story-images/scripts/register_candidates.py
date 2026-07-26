#!/usr/bin/env python3
"""Register variable-count provider outputs as unassigned sequence candidates."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


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
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def portable_project_path(project_root: Path, path: Path) -> str:
    try:
        return Path(os.path.relpath(path, project_root)).as_posix()
    except ValueError:
        return path.as_posix()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--output", action="append", required=True)
    parser.add_argument("--provider", help="Defaults to plan.provider.name.")
    parser.add_argument("--model", help="Defaults to plan.provider.model.")
    parser.add_argument("--requested-count", type=int)
    parser.add_argument("--mode", default="external-group")
    parser.add_argument("--task-id")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    if args.requested_count is not None and args.requested_count < 1:
        parser.error("--requested-count must be positive")

    plan_path = Path(args.plan).expanduser().resolve()
    try:
        plan = load_json(plan_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    project_root = (
        plan_path.parent / plan.get("paths", {}).get("projectRoot", ".")
    ).resolve()
    if not project_root.is_dir():
        parser.error(f"project root does not exist: {project_root}")

    candidate_paths = []
    for value in args.output:
        resolved = resolve_project_path(project_root, value)
        if not resolved.is_file():
            parser.error(f"candidate output does not exist: {resolved}")
        candidate_paths.append(portable_project_path(project_root, resolved))
    if len(set(candidate_paths)) != len(candidate_paths):
        parser.error("duplicate --output candidate path")

    existing_paths = {
        candidate.get("path")
        for candidate in plan.get("candidates", [])
        if isinstance(candidate, dict)
    }
    existing_paths.update(
        shot.get("output")
        for shot in plan.get("shots", [])
        if isinstance(shot, dict) and shot.get("output")
    )
    duplicates = sorted(path for path in candidate_paths if path in existing_paths)
    if duplicates:
        parser.error("already registered or assigned: " + ", ".join(duplicates))

    run_id = args.run_id or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"-{args.mode}-{uuid4().hex[:8]}"
    )
    candidates = plan.setdefault("candidates", [])
    for path in candidate_paths:
        candidates.append(
            {
                "path": path,
                "status": "unassigned",
                "suggestedShotId": None,
                "assignedShotId": None,
                "sourceRunId": run_id,
            }
        )

    provider = plan.get("provider", {})
    references = []
    continuity = plan.get("continuity", {})
    for key in ("identityReferences", "styleReferences", "settingReferences"):
        references.extend(continuity.get(key, []))
    plan.setdefault("runs", []).append(
        {
            "runId": run_id,
            "provider": args.provider or provider.get("name") or "unknown",
            "model": args.model if args.model is not None else provider.get("model", ""),
            "mode": args.mode,
            "shotIds": [],
            "referencePaths": references,
            "taskId": args.task_id,
            "seed": None,
            "requestedCount": args.requested_count,
            "returnedCount": len(candidate_paths),
            "assignmentMode": "visual-review",
            "outputs": [],
            "candidateOutputs": candidate_paths,
            "createdAt": utc_now(),
        }
    )
    write_json_atomic(plan_path, plan)
    print(
        f"registered {len(candidate_paths)} candidate(s); "
        f"requested={args.requested_count if args.requested_count is not None else 'unknown'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
