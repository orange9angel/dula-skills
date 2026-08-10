#!/usr/bin/env python3
"""Generate or edit one image via Alibaba DashScope/Bailian async API.

Replaces the `codex exec -i <ref>` imagegen path for episode bitmap work
(style tests, masters, keyframes, in-betweens, mouth/eye edit variants).
Everything downstream (diff-lock paste-back, scene code, audio) is unchanged.

Usage:
  python gen_image.py --out assets/keyframes/frame_00.png \
      --ref assets/style_master.png --ref assets/scene_room.png \
      --prompt "Use case: establishing shot ..." \
      [--prompt-file prompt.txt] [--model wan2.7-image-pro] [--size 2K] \
      [--n 1] [--watermark] [--overwrite] [--retries 2]

Requires DASHSCOPE_API_KEY in the environment. Stdlib only.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://dashscope.aliyuncs.com/api/v1"
ASYNC_GEN_URL = f"{API_BASE}/services/aigc/image-generation/generation"
TASK_URL = f"{API_BASE}/tasks"
DEFAULT_MODEL = "wan2.7-image-pro"


def encode_image(path: Path) -> str:
    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def http_json(url: str, api_key: str, payload: dict | None = None,
              headers: dict[str, str] | None = None, timeout: int = 120) -> dict:
    request_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if headers:
        request_headers.update(headers)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers=request_headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from DashScope: {body}") from exc


def extract_urls(status: dict) -> list[str]:
    urls: list[str] = []
    for choice in status.get("output", {}).get("choices") or []:
        content = choice.get("message", {}).get("content") or []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("image"), str):
                urls.append(item["image"])
    return urls


def run_task(api_key: str, model: str, content: list[dict], parameters: dict,
             label: str, poll_interval: float, timeout: float) -> tuple[str, list[str]]:
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": parameters,
    }
    response = http_json(ASYNC_GEN_URL, api_key, payload,
                         headers={"X-DashScope-Async": "enable"})
    if response.get("code"):
        raise RuntimeError(
            f"{label}: create failed: {json.dumps(response, ensure_ascii=False)}")
    task_id = response["output"]["task_id"]
    print(f"{label}: submitted task {task_id}", flush=True)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        status = http_json(f"{TASK_URL}/{task_id}", api_key)
        output = status.get("output") or {}
        state = output.get("task_status")
        if state == "SUCCEEDED":
            urls = extract_urls(status)
            if not urls:
                raise RuntimeError(f"{label}: task succeeded but returned no image")
            return task_id, urls
        if state in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(
                f"{label}: task {state}: {json.dumps(status, ensure_ascii=False)}")
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


def image_size(path: Path) -> tuple[int, int] | None:
    """Read PNG/JPEG pixel dimensions without third-party libraries."""
    data = path.read_bytes()[:64 * 1024]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
            i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="output image path")
    parser.add_argument("--prompt", help="prompt text")
    parser.add_argument("--prompt-file", help="read prompt text from file (overrides --prompt)")
    parser.add_argument("--ref", action="append", default=[],
                        help="reference image, repeatable; order = weight order "
                             "(master identity first, nearest approved frame next)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default="2K", help="provider size token, e.g. 1K/2K/4K")
    parser.add_argument("--n", type=int, default=None, help="requested image count")
    parser.add_argument("--watermark", action="store_true", help="keep provider watermark")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--retries", type=int, default=2,
                        help="total attempts including the first (default 2)")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    out = Path(args.out)
    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt or not prompt.strip():
        parser.error("empty prompt (use --prompt or --prompt-file)")

    if out.exists() and not args.overwrite:
        print(f"skip: {out} already exists (use --overwrite to regenerate)")
        return 0

    refs = []
    for value in args.ref:
        path = Path(value)
        if not path.is_file():
            parser.error(f"reference does not exist: {path}")
        refs.append(path)

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        parser.error("DASHSCOPE_API_KEY is not set")

    content = [{"image": encode_image(path)} for path in refs]
    content.append({"text": prompt})
    parameters = {"size": args.size, "watermark": bool(args.watermark)}
    if args.n is not None:
        parameters["n"] = args.n

    label = out.stem
    last_error: Exception | None = None
    for attempt in range(1, max(1, args.retries) + 1):
        try:
            task_id, urls = run_task(api_key, args.model, content, parameters,
                                     label, args.poll_interval, args.timeout)
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001 - report and retry
            last_error = exc
            print(f"{label}: attempt {attempt} failed: {exc}", file=sys.stderr, flush=True)
    if last_error is not None:
        return 1

    # Multiple returns: first takes the requested name, surplus goes to _candidates/.
    download(urls[0], out)
    for index, url in enumerate(urls[1:], start=2):
        candidate = out.parent / "_candidates" / f"{out.stem}_{index:02d}.png"
        download(url, candidate)
        print(f"{label}: surplus candidate -> {candidate}", flush=True)

    size = image_size(out)
    summary = {
        "out": str(out),
        "pixels": f"{size[0]}x{size[1]}" if size else "unknown",
        "model": args.model,
        "taskId": task_id,
        "returnedCount": len(urls),
        "refs": [str(p) for p in refs],
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
