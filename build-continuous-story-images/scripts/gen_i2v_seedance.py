#!/usr/bin/env python3
"""Generate one short video clip from a first-frame image via Volcano Engine
Ark Seedance image-to-video (doubao-seedance-1-0-pro by default), then
optionally extract it into a 12fps cel PNG sequence for the 2D keyframe
pipeline. Seedance variant of gen_i2v.py (DashScope/wan2.6-i2v-flash); same
CLI contract so episodes can A/B the two providers on the same keyframe.

Why this exists: wan2.6-i2v-flash is the cheap flash tier and lets the
character drift off-model during fast motion (running). Seedance 1.0 pro
ranks at the top of public I2V benchmarks for motion consistency; use it for
shots where flash-tier drift is visible.

Cost guard: billing is per output token; tokens ~= duration * W * H * fps /
1024 (~21600 tokens/s at 720p 16:9 24fps). Unit prices (CNY/1M tokens,
2026-08 火山方舟刊例):
  doubao-seedance-1-0-pro-fast  4.2   (~0.09/s 720p, cheapest)
  doubao-seedance-1-5-pro       8.0   (silent; ~0.17/s)
  doubao-seedance-1-0-pro      15.0   (~0.32/s, default: best consistency/price)
  doubao-seedance-2-0-mini     23.0   (~0.50/s)
  doubao-seedance-2-0-fast     37.0   (~0.80/s)
  doubao-seedance-2-0          46.0   (~0.99/s, 1080p capable)
Seedance 1.0 pro only supports 5s or 10s clips; 2.x supports 4-15s.

Usage:
  python gen_i2v_seedance.py --out assets/i2v/cat_run.mp4 \
      --first-frame assets/keyframes/frame_run_01.png \
      --prompt "The orange tabby cat runs along the riverbank ..." \
      [--duration 5] [--resolution 720p] [--model doubao-seedance-1-0-pro-250528] \
      [--seed 12345] [--camera-fixed] [--overwrite] [--retries 2] \
      [--extract-cels assets/i2v/cat_run --fps 12]

Requires ARK_API_KEY in the environment (火山方舟 API key). Stdlib only for
the API part; --extract-cels needs ffmpeg on PATH. Not covered by any
automated test against the live API yet — verify on one cheap clip first.
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

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedance-2-0-260128"

# CNY per 1M output tokens, matched by model-name prefix (火山方舟刊例 2026-08).
TOKEN_PRICES = [
    ("doubao-seedance-1-0-pro-fast", 4.2),
    ("doubao-seedance-1-0-pro", 15.0),
    ("doubao-seedance-1-0-lite", 3.0),
    ("doubao-seedance-1-5-pro", 8.0),  # silent tier
    ("doubao-seedance-2-0-mini", 23.0),
    ("doubao-seedance-2-0-fast", 37.0),
    ("doubao-seedance-2-0", 46.0),
]


def encode_image(path: Path) -> str:
    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def http_json(url: str, api_key: str, payload: dict | None = None,
              timeout: int = 120) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from Ark: {body}") from exc


def run_task(base_url: str, api_key: str, model: str, content: list[dict],
             parameters: dict, label: str, poll_interval: float,
             timeout: float) -> tuple[str, str, dict]:
    payload = {"model": model, "content": content, **parameters}
    response = http_json(f"{base_url}/contents/generations/tasks", api_key, payload)
    task_id = response.get("id")
    if not task_id:
        raise RuntimeError(
            f"{label}: create failed: {json.dumps(response, ensure_ascii=False)}")
    print(f"{label}: submitted task {task_id}", flush=True)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        status = http_json(f"{base_url}/contents/generations/tasks/{task_id}", api_key)
        state = status.get("status")
        if state == "succeeded":
            video_url = (status.get("content") or {}).get("video_url")
            if not video_url:
                raise RuntimeError(f"{label}: task succeeded but returned no video_url")
            return task_id, video_url, status.get("usage") or {}
        if state in {"failed", "cancelled", "expired"}:
            raise RuntimeError(
                f"{label}: task {state}: {json.dumps(status, ensure_ascii=False)}")
        print(f"{label}: {state} ...", flush=True)
    raise RuntimeError(f"{label}: task timed out after {timeout:.0f}s")


def download(url: str, destination: Path) -> None:
    # video_url is a pre-signed link: no Authorization header.
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


def estimate_cost(model: str, usage: dict) -> float | None:
    tokens = usage.get("completion_tokens")
    if not tokens:
        return None
    for prefix, price in TOKEN_PRICES:
        if model.startswith(prefix):
            return tokens / 1_000_000 * price
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="output .mp4 path")
    parser.add_argument("--first-frame", help="first-frame image (PNG/JPG); required unless --ref is used")
    parser.add_argument("--ref", action="append", default=[],
                        help="Seedance 2.x only: reference image (repeatable, up to 9). "
                             "Switches to multi-modal reference mode — mutually exclusive "
                             "with --first-frame, so the output does NOT start from an "
                             "exact frame; use for character-identity experiments.")
    parser.add_argument("--prompt", help="motion prompt text")
    parser.add_argument("--prompt-file", help="read prompt text from file (overrides --prompt)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--resolution", default="720p", help="480p, 720p or 1080p")
    parser.add_argument("--duration", type=int, default=5,
                        help="seconds; 1.0 pro supports 5 or 10, 2.x supports 4..15 (default 5, cost guard)")
    parser.add_argument("--ratio", default="adaptive",
                        help="16:9, 4:3, 1:1, 3:4, 9:16, 21:9 or adaptive (default adaptive: follow input image, no cropping)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--camera-fixed", action="store_true",
                        help="Seedance 1.x only: lock the camera (matches the cel pipeline's static-shot rule)")
    parser.add_argument("--audio", action="store_true",
                        help="Seedance 1.5/2.x only: generate synchronized audio (costs more); off = silent")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--retries", type=int, default=2,
                        help="total attempts including the first (default 2)")
    parser.add_argument("--poll-interval", type=float, default=20.0)
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

    first_frame = Path(args.first_frame) if args.first_frame else None
    if first_frame and not first_frame.is_file():
        parser.error(f"first frame does not exist: {first_frame}")
    refs = [Path(r) for r in args.ref]
    for ref in refs:
        if not ref.is_file():
            parser.error(f"reference image does not exist: {ref}")
    if first_frame and refs:
        parser.error("--first-frame and --ref are mutually exclusive in Seedance "
                     "(first-frame mode vs multi-modal reference mode)")
    if not first_frame and not refs:
        parser.error("need --first-frame or at least one --ref")

    if out.exists() and not args.overwrite:
        print(f"skip: {out} already exists (use --overwrite to regenerate)")
    else:
        api_key = os.environ.get("ARK_API_KEY", "")
        if not api_key:
            parser.error("ARK_API_KEY is not set (火山方舟 API key)")
        base_url = os.environ.get("ARK_BASE_URL", DEFAULT_BASE_URL)

        content = [{"type": "text", "text": prompt}]
        if first_frame:
            content.append({"type": "image_url",
                            "image_url": {"url": encode_image(first_frame)},
                            "role": "first_frame"})
        for ref in refs:
            content.append({"type": "image_url",
                            "image_url": {"url": encode_image(ref)},
                            "role": "reference_image"})
        parameters = {
            "resolution": args.resolution,
            "duration": args.duration,
            "ratio": args.ratio,
            "watermark": False,
        }
        if "seedance-1-0" in args.model:
            # Seedance 1.0: silent by design; supports camera_fixed, not generate_audio.
            if args.camera_fixed:
                parameters["camera_fixed"] = True
        else:
            # 2.x: generate_audio defaults to TRUE server-side — always pin it off
            # unless the caller explicitly wants sound (audio costs more).
            parameters["generate_audio"] = bool(args.audio)
        if args.seed is not None:
            parameters["seed"] = args.seed

        label = out.stem
        last_error: Exception | None = None
        task_id, video_url, usage = None, None, {}
        for attempt in range(1, max(1, args.retries) + 1):
            try:
                task_id, video_url, usage = run_task(
                    base_url, api_key, args.model, content, parameters,
                    label, args.poll_interval, args.timeout)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001 - report and retry
                last_error = exc
                print(f"{label}: attempt {attempt} failed: {exc}", file=sys.stderr, flush=True)
        if last_error is not None:
            return 1

        download(video_url, out)
        cost = estimate_cost(args.model, usage)
        print(json.dumps({
            "out": str(out), "model": args.model, "taskId": task_id,
            "resolution": args.resolution, "duration": args.duration,
            "usage": usage,
            "estimatedCostCny": round(cost, 4) if cost is not None else None,
        }, ensure_ascii=False), flush=True)

    if args.extract_cels:
        count = extract_cels(out, Path(args.extract_cels), args.fps)
        print(f"cels: {count} frames -> {args.extract_cels} (fps={args.fps})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
