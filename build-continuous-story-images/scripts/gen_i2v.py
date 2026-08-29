#!/usr/bin/env python3
"""Generate one short video clip from a first-frame image via Alibaba
DashScope/Bailian image-to-video (wan2.6-i2v-flash by default), then
optionally extract it into a 12fps cel PNG sequence for the 2D keyframe
pipeline (see walk-director / cat_leads_e02 storyboard).

Cost guard: default is 3 seconds at 720P silent (audio=false) =
0.15 CNY/s -> ~0.45 CNY per clip. Keep --duration 3 unless told otherwise.

Usage:
  python gen_i2v.py --out assets/i2v/cat_wall_walk.mp4 \
      --first-frame assets/keyframes/frame_wall_01.png \
      --prompt "The orange tabby cat walks lightly along the wall top ..." \
      [--duration 3] [--resolution 720P] [--model wan2.6-i2v-flash] \
      [--seed 12345] [--prompt-extend] [--overwrite] [--retries 2] \
      [--extract-cels assets/i2v/cat_wall_walk --fps 12]

Requires DASHSCOPE_API_KEY in the environment. Stdlib only for the API part;
--extract-cels needs ffmpeg on PATH.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://dashscope.aliyuncs.com/api/v1"
ASYNC_VIDEO_URL = f"{API_BASE}/services/aigc/video-generation/video-synthesis"
TASK_URL = f"{API_BASE}/tasks"
DEFAULT_MODEL = "wan2.6-i2v-flash"


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


def run_task(api_key: str, model: str, payload_input: dict, parameters: dict,
             label: str, poll_interval: float, timeout: float) -> tuple[str, str, dict]:
    payload = {"model": model, "input": payload_input, "parameters": parameters}
    response = http_json(ASYNC_VIDEO_URL, api_key, payload,
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
            video_url = output.get("video_url")
            if not video_url:
                raise RuntimeError(f"{label}: task succeeded but returned no video_url")
            return task_id, video_url, status.get("usage") or {}
        if state in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(
                f"{label}: task {state}: {json.dumps(status, ensure_ascii=False)}")
        print(f"{label}: {state} ...", flush=True)
    raise RuntimeError(f"{label}: task timed out after {timeout:.0f}s")


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            temporary.write_bytes(response.read())
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def extract_cels(video: Path, cel_dir: Path, fps: int) -> int:
    """Extract the clip into an f_0001.png cel sequence. Returns cel count."""
    cel_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(cel_dir / "f_%04d.png")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vf", f"fps={fps}", pattern],
        check=True, capture_output=True,
    )
    return len(list(cel_dir.glob("f_*.png")))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="output .mp4 path")
    parser.add_argument("--first-frame", required=True, help="first-frame image (PNG/JPG)")
    parser.add_argument("--prompt", help="motion prompt text")
    parser.add_argument("--prompt-file", help="read prompt text from file (overrides --prompt)")
    parser.add_argument("--negative-prompt", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--resolution", default="720P", help="720P or 1080P")
    parser.add_argument("--duration", type=int, default=3,
                        help="seconds; wan2.6-i2v(-flash) supports 2..15 (default 3, cost guard)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--prompt-extend", action="store_true",
                        help="enable provider smart prompt rewrite (off by default to keep style control)")
    parser.add_argument("--audio", action="store_true",
                        help="wan2.6-i2v-flash only: generate audio (costs more); off = silent")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--retries", type=int, default=2,
                        help="total attempts including the first (default 2)")
    parser.add_argument("--poll-interval", type=float, default=15.0)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--extract-cels", default=None,
                        help="directory to extract cel PNGs into (ffmpeg fps filter)")
    parser.add_argument("--fps", type=int, default=12, help="cel extraction fps (default 12)")
    args = parser.parse_args()

    out = Path(args.out)
    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt or not prompt.strip():
        parser.error("empty prompt (use --prompt or --prompt-file)")

    first_frame = Path(args.first_frame)
    if not first_frame.is_file():
        parser.error(f"first frame does not exist: {first_frame}")

    if out.exists() and not args.overwrite:
        print(f"skip: {out} already exists (use --overwrite to regenerate)")
    else:
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            parser.error("DASHSCOPE_API_KEY is not set")

        payload_input = {"prompt": prompt, "img_url": encode_image(first_frame)}
        if args.negative_prompt:
            payload_input["negative_prompt"] = args.negative_prompt
        parameters = {
            "resolution": args.resolution,
            "duration": args.duration,
            "prompt_extend": bool(args.prompt_extend),
            "watermark": False,
        }
        if args.model == "wan2.6-i2v-flash":
            parameters["audio"] = bool(args.audio)
        if args.seed is not None:
            parameters["seed"] = args.seed

        label = out.stem
        last_error: Exception | None = None
        task_id, video_url, usage = None, None, {}
        for attempt in range(1, max(1, args.retries) + 1):
            try:
                task_id, video_url, usage = run_task(
                    api_key, args.model, payload_input, parameters,
                    label, args.poll_interval, args.timeout)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001 - report and retry
                last_error = exc
                print(f"{label}: attempt {attempt} failed: {exc}", file=sys.stderr, flush=True)
        if last_error is not None:
            return 1

        download(video_url, out)
        print(json.dumps({
            "out": str(out), "model": args.model, "taskId": task_id,
            "resolution": args.resolution, "duration": args.duration,
            "usage": usage,
        }, ensure_ascii=False), flush=True)

    if args.extract_cels:
        count = extract_cels(out, Path(args.extract_cels), args.fps)
        print(f"cels: {count} frames -> {args.extract_cels} (fps={args.fps})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
