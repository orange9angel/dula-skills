#!/usr/bin/env python3
"""Run a compiled continuity request with Alibaba DashScope/Bailian."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


API_BASE = "https://dashscope.aliyuncs.com/api/v1"
ASYNC_GEN_URL = f"{API_BASE}/services/aigc/image-generation/generation"
TASK_URL = f"{API_BASE}/tasks"


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return data


def write_json_atomic(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def resolve_from(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def portable_project_path(project_root: Path, path: Path) -> str:
    try:
        return Path(os.path.relpath(path, project_root)).as_posix()
    except ValueError:
        return path.as_posix()


def encode_image(path: Path) -> str:
    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def http_json(
    url: str,
    api_key: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict:
    request_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if headers:
        request_headers.update(headers)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from DashScope: {body}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("DashScope returned a non-object JSON response")
    return result


def extract_urls(status: dict) -> list[str]:
    urls: list[str] = []
    for choice in status.get("output", {}).get("choices") or []:
        content = choice.get("message", {}).get("content") or []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("image"), str):
                urls.append(item["image"])
    return urls


def run_task(
    *,
    api_key: str,
    model: str,
    content: list[dict],
    parameters: dict,
    label: str,
    poll_interval: float,
    timeout: float,
) -> tuple[str, list[str]]:
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": parameters,
    }
    response = http_json(
        ASYNC_GEN_URL,
        api_key,
        payload,
        headers={"X-DashScope-Async": "enable"},
    )
    if response.get("code"):
        raise RuntimeError(
            f"{label}: create failed: {json.dumps(response, ensure_ascii=False)}"
        )
    try:
        task_id = response["output"]["task_id"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            f"{label}: missing task id: {json.dumps(response, ensure_ascii=False)}"
        ) from exc

    print(f"{label}: submitted task {task_id}", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        status = http_json(f"{TASK_URL}/{task_id}", api_key)
        output = status.get("output") or {}
        state = output.get("task_status")
        if state == "SUCCEEDED":
            urls = extract_urls(status)
            print(f"{label}: succeeded with {len(urls)} image(s)", flush=True)
            return task_id, urls
        if state in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(
                f"{label}: task {state}: {json.dumps(status, ensure_ascii=False)}"
            )
    raise RuntimeError(f"{label}: task timed out after {timeout:.0f}s")


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=180) as response:
            temporary.write_bytes(response.read())
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_content(reference_paths: list[Path], prompt: str) -> list[dict]:
    content = [{"image": encode_image(path)} for path in reference_paths]
    content.append({"text": prompt})
    return content


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_run_id(mode: str) -> str:
    return (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"-{mode}-{uuid4().hex[:8]}"
    )


def run_record(
    *,
    run_id: str,
    mode: str,
    provider: str,
    model: str,
    task_id: str,
    shot_ids: list[str],
    reference_paths: list[str],
    requested_count: int | None,
    returned_count: int,
    assignment_mode: str,
    outputs: list[str],
    candidate_outputs: list[str],
) -> dict:
    return {
        "runId": run_id,
        "provider": provider,
        "model": model,
        "mode": mode,
        "shotIds": shot_ids,
        "referencePaths": reference_paths,
        "taskId": task_id,
        "seed": None,
        "requestedCount": requested_count,
        "returnedCount": returned_count,
        "assignmentMode": assignment_mode,
        "outputs": outputs,
        "candidateOutputs": candidate_outputs,
        "createdAt": utc_now(),
    }


def save_candidates(
    *,
    urls: list[str],
    candidate_directory: Path,
    project_root: Path,
    run_id: str,
    suggested_shot_id: str | None,
) -> tuple[list[dict], list[str]]:
    records = []
    paths = []
    for index, url in enumerate(urls, start=1):
        destination = candidate_directory / f"{run_id}_{index:02d}.png"
        download(url, destination)
        manifest_path = portable_project_path(project_root, destination)
        records.append(
            {
                "path": manifest_path,
                "status": "unassigned",
                "suggestedShotId": suggested_shot_id,
                "assignedShotId": None,
                "sourceRunId": run_id,
            }
        )
        paths.append(manifest_path)
        print(f"candidate: wrote {destination}", flush=True)
    return records, paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    request_path = Path(args.request).expanduser().resolve()
    try:
        request = load_json(request_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    provider = request.get("provider") or {}
    provider_name = str(provider.get("name", "")).lower()
    if provider_name not in {"dashscope", "bailian", "aliyun-bailian"}:
        parser.error(f"request provider is not DashScope/Bailian: {provider_name!r}")
    model = provider.get("model") or "wan2.7-image-pro"
    capabilities = provider.get("capabilities") or {}
    options = dict(provider.get("options") or {})
    allowed_options = {"size", "watermark"}
    unknown_options = sorted(set(options) - allowed_options)
    if unknown_options:
        parser.error(
            "unsupported DashScope option(s): " + ", ".join(unknown_options)
        )

    project_root = (request_path.parent / request.get("projectRoot", ".")).resolve()
    if not project_root.is_dir():
        parser.error(f"project root does not exist: {project_root}")
    plan_path = (request_path.parent / request["sequencePlan"]).resolve()
    if not plan_path.is_file():
        parser.error(f"sequence plan does not exist: {plan_path}")

    references = request.get("references") or []
    master_paths: list[Path] = []
    master_manifest_paths: list[str] = []
    for reference in references:
        value = reference.get("path")
        if not isinstance(value, str) or not value:
            parser.error("every reference must contain a non-empty path")
        resolved = resolve_from(project_root, value)
        if not resolved.is_file():
            parser.error(f"reference does not exist: {resolved}")
        master_paths.append(resolved)
        master_manifest_paths.append(value)

    shots = request.get("shots") or []
    if not shots:
        parser.error("request contains no shots")
    max_group = request.get("strategy", {}).get("maxShotsPerGroup", 5)
    if len(shots) > max_group:
        parser.error(
            f"{len(shots)} shots exceed maxShotsPerGroup={max_group}; "
            "split the action into overlapping sequence plans"
        )

    output_paths = {
        shot["id"]: resolve_from(project_root, shot["output"]) for shot in shots
    }
    existing = [
        shot["id"] for shot in shots if output_paths[shot["id"]].is_file()
    ]
    group_enabled = (
        request.get("strategy", {}).get("preferSequentialGroup", True)
        and capabilities.get("sequentialGroup") is True
        and len(shots) > 1
    )
    group_request = request.get("group", {})
    requested_count = group_request.get("requestedCount")
    assignment_mode = request.get("resultPolicy", {}).get(
        "assignmentMode", "visual-review"
    )

    summary = {
        "provider": provider_name,
        "model": model,
        "strategy": "sequential-group" if group_enabled else "per-shot",
        "shotIds": [shot["id"] for shot in shots],
        "masterReferences": master_manifest_paths,
        "existingOutputs": existing,
        "desiredCount": group_request.get("desiredCount", len(shots)),
        "requestedCount": requested_count,
        "returnedCount": "unknown until execution",
        "assignmentMode": assignment_mode,
        "options": options,
        "networkCall": not args.dry_run,
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        parser.error("DASHSCOPE_API_KEY is not set")

    plan = load_json(plan_path)
    plan_shots = {shot["id"]: shot for shot in plan.get("shots", [])}
    produced: dict[str, str] = {}
    run_records: list[dict] = []
    candidate_records: list[dict] = []
    manual_assignment_required = False
    candidate_directory = resolve_from(
        project_root,
        request.get(
            "candidateDirectory",
            (Path(request["shots"][0]["output"]).parent / "_candidates").as_posix(),
        ),
    )

    can_group_now = group_enabled and (args.overwrite or not existing)
    if can_group_now:
        parameters = {**options, "enable_sequential": True}
        if requested_count is not None:
            parameters["n"] = requested_count
        task_id, urls = run_task(
            api_key=api_key,
            model=model,
            content=build_content(master_paths, request["group"]["prompt"]),
            parameters=parameters,
            label="group",
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        group_run_id = new_run_id("sequential-group")
        group_outputs = []
        group_ids = []
        group_candidate_paths = []
        if assignment_mode == "position":
            for shot, url in zip(shots, urls):
                destination = output_paths[shot["id"]]
                download(url, destination)
                produced[shot["id"]] = shot["output"]
                group_outputs.append(shot["output"])
                group_ids.append(shot["id"])
                print(f"{shot['id']}: wrote {destination}", flush=True)
            extra_urls = urls[len(shots) :]
            if extra_urls:
                records, group_candidate_paths = save_candidates(
                    urls=extra_urls,
                    candidate_directory=candidate_directory,
                    project_root=project_root,
                    run_id=group_run_id,
                    suggested_shot_id=None,
                )
                candidate_records.extend(records)
        else:
            records, group_candidate_paths = save_candidates(
                urls=urls,
                candidate_directory=candidate_directory,
                project_root=project_root,
                run_id=group_run_id,
                suggested_shot_id=None,
            )
            candidate_records.extend(records)
            manual_assignment_required = bool(urls)
        run_records.append(
            run_record(
                run_id=group_run_id,
                mode="sequential-group",
                provider=provider_name,
                model=model,
                task_id=task_id,
                shot_ids=group_ids,
                reference_paths=master_manifest_paths,
                requested_count=requested_count,
                returned_count=len(urls),
                assignment_mode=assignment_mode,
                outputs=group_outputs,
                candidate_outputs=group_candidate_paths,
            )
        )

    if not args.no_fallback and not manual_assignment_required:
        for shot in shots:
            destination = output_paths[shot["id"]]
            if destination.is_file() and not args.overwrite:
                continue
            if shot["id"] in produced:
                continue

            fallback_paths = list(master_paths)
            fallback_manifest_paths = list(master_manifest_paths)
            continuity_reference = shot.get("continuityReference")
            if continuity_reference:
                continuity_path = resolve_from(project_root, continuity_reference)
                if not continuity_path.is_file():
                    raise RuntimeError(
                        f"{shot['id']}: approved continuity reference is missing: "
                        f"{continuity_path}"
                    )
                if continuity_path not in fallback_paths:
                    fallback_paths.append(continuity_path)
                    fallback_manifest_paths.append(continuity_reference)

            parameters = dict(options)
            fallback_requested_count = (
                1 if capabilities.get("acceptsRequestedCount") is True else None
            )
            if fallback_requested_count is not None:
                parameters["n"] = fallback_requested_count
            task_id, urls = run_task(
                api_key=api_key,
                model=model,
                content=build_content(fallback_paths, shot["prompt"]),
                parameters=parameters,
                label=shot["id"],
                poll_interval=args.poll_interval,
                timeout=args.timeout,
            )
            if not urls:
                raise RuntimeError(f"{shot['id']}: provider returned no image")
            fallback_run_id = new_run_id("per-shot-fallback")
            fallback_outputs = []
            fallback_candidate_paths = []
            fallback_assignment_mode = "position"
            if len(urls) == 1:
                download(urls[0], destination)
                produced[shot["id"]] = shot["output"]
                fallback_outputs.append(shot["output"])
                print(f"{shot['id']}: wrote {destination}", flush=True)
            else:
                records, fallback_candidate_paths = save_candidates(
                    urls=urls,
                    candidate_directory=candidate_directory,
                    project_root=project_root,
                    run_id=fallback_run_id,
                    suggested_shot_id=shot["id"],
                )
                candidate_records.extend(records)
                fallback_assignment_mode = "visual-review"
                manual_assignment_required = True
            run_records.append(
                run_record(
                    run_id=fallback_run_id,
                    mode="per-shot-fallback",
                    provider=provider_name,
                    model=model,
                    task_id=task_id,
                    shot_ids=[shot["id"]],
                    reference_paths=fallback_manifest_paths,
                    requested_count=fallback_requested_count,
                    returned_count=len(urls),
                    assignment_mode=fallback_assignment_mode,
                    outputs=fallback_outputs,
                    candidate_outputs=fallback_candidate_paths,
                )
            )
            if manual_assignment_required:
                break

    for shot_id, output in produced.items():
        if shot_id not in plan_shots:
            raise RuntimeError(f"compiled request references unknown plan shot: {shot_id}")
        plan_shots[shot_id]["output"] = output
        plan_shots[shot_id]["status"] = "generated"
        plan_shots[shot_id].setdefault("review", {"issues": [], "notes": ""})
    plan.setdefault("runs", []).extend(run_records)
    plan.setdefault("candidates", []).extend(candidate_records)
    if produced or run_records or candidate_records:
        write_json_atomic(plan_path, plan)

    if manual_assignment_required:
        print(
            f"done with {len(candidate_records)} unassigned candidate(s); "
            "review and map them before generating missing shots"
        )
        return 0

    missing = [
        shot["id"] for shot in shots if not output_paths[shot["id"]].is_file()
    ]
    if missing:
        print("Missing outputs: " + ", ".join(missing))
        return 1
    print(f"done: {len(shots)} output(s); review before marking accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
