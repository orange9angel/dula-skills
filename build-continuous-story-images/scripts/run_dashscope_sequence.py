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


def run_record(
    *,
    mode: str,
    provider: str,
    model: str,
    task_id: str,
    shot_ids: list[str],
    reference_paths: list[str],
    outputs: list[str],
) -> dict:
    return {
        "runId": f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{mode}",
        "provider": provider,
        "model": model,
        "mode": mode,
        "shotIds": shot_ids,
        "referencePaths": reference_paths,
        "taskId": task_id,
        "seed": None,
        "outputs": outputs,
        "createdAt": utc_now(),
    }


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

    summary = {
        "provider": provider_name,
        "model": model,
        "strategy": "sequential-group" if group_enabled else "per-shot",
        "shotIds": [shot["id"] for shot in shots],
        "masterReferences": master_manifest_paths,
        "existingOutputs": existing,
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

    can_group_now = group_enabled and (args.overwrite or not existing)
    if can_group_now:
        parameters = {**options, "enable_sequential": True, "n": len(shots)}
        task_id, urls = run_task(
            api_key=api_key,
            model=model,
            content=build_content(master_paths, request["group"]["prompt"]),
            parameters=parameters,
            label="group",
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        group_outputs = []
        group_ids = []
        for shot, url in zip(shots, urls):
            destination = output_paths[shot["id"]]
            download(url, destination)
            produced[shot["id"]] = shot["output"]
            group_outputs.append(shot["output"])
            group_ids.append(shot["id"])
            print(f"{shot['id']}: wrote {destination}", flush=True)
        run_records.append(
            run_record(
                mode="sequential-group",
                provider=provider_name,
                model=model,
                task_id=task_id,
                shot_ids=group_ids,
                reference_paths=master_manifest_paths,
                outputs=group_outputs,
            )
        )

    if not args.no_fallback:
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

            parameters = {**options, "n": 1}
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
            download(urls[0], destination)
            produced[shot["id"]] = shot["output"]
            print(f"{shot['id']}: wrote {destination}", flush=True)
            run_records.append(
                run_record(
                    mode="per-shot-fallback",
                    provider=provider_name,
                    model=model,
                    task_id=task_id,
                    shot_ids=[shot["id"]],
                    reference_paths=fallback_manifest_paths,
                    outputs=[shot["output"]],
                )
            )

    for shot_id, output in produced.items():
        if shot_id not in plan_shots:
            raise RuntimeError(f"compiled request references unknown plan shot: {shot_id}")
        plan_shots[shot_id]["output"] = output
        plan_shots[shot_id]["status"] = "generated"
        plan_shots[shot_id].setdefault("review", {"issues": [], "notes": ""})
    plan.setdefault("runs", []).extend(run_records)
    if produced:
        write_json_atomic(plan_path, plan)

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
