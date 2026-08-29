#!/usr/bin/env python3
"""Motion-transfer video: make a subject (reference image) perform the motion
of a reference video, via Volcano Ark Seedance 2.0 multi-modal reference mode.

Usage:
  python gen_motion_transfer.py --image cat.png --video-url https://.../dance.mp4 \
      --out cat_dance.mp4 --prompt "The cat performs the exact same dance ..."

Notes (production-verified 2026-08-29):
- reference_video must be a PUBLIC web URL; base64 data URLs are rejected
  ("reference_video must be provided as a web url"). Upload to a public host
  first (catbox.moe works). reference_image DOES accept base64 data URLs.
- Cost: tokens ~ duration*W*H*24/1024 + input video tokens. 720p 5s with a
  video input: ~368k tokens -> 2.0 standard ~¥11.4 (¥31/M), 2.0 mini ~¥5.2
  (¥14/M, ~¥2 during promos). mini quality was fine for meme content and
  ~5x faster (~1 min vs ~5 min).
- Audio: keep generate_audio=false; mux the source video's track back with
  ffmpeg for free (the generated audio won't be the original song anyway):
  ffmpeg -i out.mp4 -i source.mp4 -map 0:v -map 1:a -c:v copy -c:a aac -shortest
- Real-person source videos: don't publish commercially; Ark's 素材库 path
  requires real-person liveness consent. Experimental use only.

Requires ARK_API_KEY in the environment.
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

BASE_URL = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
DEFAULT_MODEL = "doubao-seedance-2-0-mini-260615"


def encode_image(path: Path) -> str:
    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def http_json(url: str, api_key: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from Ark: {exc.read().decode('utf-8', 'replace')[:600]}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="subject reference image (PNG/JPG)")
    parser.add_argument("--video-url", required=True, help="public URL of the motion reference video")
    parser.add_argument("--out", required=True, help="output .mp4 path")
    parser.add_argument("--prompt", required=True, help="transfer instruction prompt")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--resolution", default="720p")
    parser.add_argument("--ratio", default="adaptive")
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--audio", action="store_true", help="generate model audio (off = silent)")
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--poll-interval", type=float, default=20.0)
    args = parser.parse_args()

    api_key = os.environ.get("ARK_API_KEY", "")
    if not api_key:
        parser.error("ARK_API_KEY is not set")

    payload = {
        "model": args.model,
        "content": [
            {"type": "text", "text": args.prompt},
            {"type": "image_url",
             "image_url": {"url": encode_image(Path(args.image))},
             "role": "reference_image"},
            {"type": "video_url", "video_url": {"url": args.video_url},
             "role": "reference_video"},
        ],
        "resolution": args.resolution,
        "ratio": args.ratio,
        "duration": args.duration,
        "generate_audio": bool(args.audio),
        "watermark": False,
    }
    resp = http_json(f"{BASE_URL}/contents/generations/tasks", api_key, payload)
    task_id = resp.get("id")
    if not task_id:
        raise RuntimeError(f"create failed: {json.dumps(resp, ensure_ascii=False)}")
    print(f"submitted {task_id}", flush=True)

    deadline = time.monotonic() + args.timeout
    status = {}
    while time.monotonic() < deadline:
        time.sleep(args.poll_interval)
        status = http_json(f"{BASE_URL}/contents/generations/tasks/{task_id}", api_key)
        state = status.get("status")
        print(state, flush=True)
        if state == "succeeded":
            break
        if state in {"failed", "cancelled", "expired"}:
            raise RuntimeError(f"task {state}: {json.dumps(status, ensure_ascii=False)[:500]}")
    else:
        raise RuntimeError(f"timed out after {args.timeout}s")

    video_url = (status.get("content") or {}).get("video_url")
    if not video_url:
        raise RuntimeError("succeeded but no video_url")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(video_url, out)
    print(json.dumps({"out": str(out), "taskId": task_id,
                      "usage": status.get("usage")}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
