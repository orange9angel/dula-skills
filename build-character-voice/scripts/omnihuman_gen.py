#!/usr/bin/env python3
"""OmniHuman 1.5 (即梦数字人) image+audio -> lip-synced video, E04 pilot.

Volcano 视觉智能 (CV) task API: CVSubmitTask / CVGetResult via the official
volcengine SDK's VisualService, req_key=jimeng_realman_avatar_picture_omni_v15.

Auth: IAM sub-user AccessKey pair (env VOLC_ACCESSKEY / VOLC_SECRETKEY,
store in dula-story/.env.cv, gitignored). Sub-user needs CVFullAccess.

NOTE: image_url/audio_url must be publicly reachable URLs (no local files,
no documented base64 field on this endpoint). Upload local assets first
(e.g. TOS) or serve them; see the pilot runbook in V1_NOTES.md.

Usage:
  omnihuman_gen.py --image <url> --audio <url> --out out.mp4 \
      [--prompt "…"] [--seed 12345] [--resolution 720] [--timeout 900]

Run with the workspace venv:  dula-story/.venv/Scripts/python.exe
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REQ_KEY = "jimeng_realman_avatar_picture_omni_v15"
AK_ENV = "VOLC_ACCESSKEY"
SK_ENV = "VOLC_SECRETKEY"


class OmniHumanError(RuntimeError):
    pass


def _client():
    try:
        from volcengine.visual.VisualService import VisualService
    except ImportError as exc:
        raise OmniHumanError(
            "volcengine SDK missing; install into the project venv: "
            "dula-story/.venv/Scripts/python.exe -m pip install volcengine"
        ) from exc
    ak = os.environ.get(AK_ENV, "")
    sk = os.environ.get(SK_ENV, "")
    if not ak or not sk:
        raise OmniHumanError(f"{AK_ENV}/{SK_ENV} are not set (IAM sub-user key pair)")
    client = VisualService()
    client.set_ak(ak)
    client.set_sk(sk)
    return client


def submit(client, *, image_url: str, audio_url: str, prompt: str | None,
           seed: int, resolution: int) -> str:
    form: dict = {
        "req_key": REQ_KEY,
        "image_url": image_url,
        "audio_url": audio_url,
        "seed": seed,
        "output_resolution": resolution,
        "pe_fast_mode": resolution == 720,
    }
    if prompt:
        form["prompt"] = prompt
    resp = client.cv_submit_task(form)
    task_id = (resp.get("data") or {}).get("task_id")
    if not task_id:
        raise OmniHumanError(f"submit failed: {json.dumps(resp, ensure_ascii=False)[:400]}")
    return task_id


def poll(client, task_id: str, timeout: float, interval: float = 10.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.cv_get_result({"req_key": REQ_KEY, "task_id": task_id})
        data = resp.get("data") or {}
        status = data.get("status")
        if status == "done":
            video_url = data.get("video_url")
            if not video_url:
                raise OmniHumanError(f"task done without video_url: {json.dumps(resp)[:300]}")
            return video_url
        if status in ("not_found", "expired"):
            raise OmniHumanError(f"task {status}: {json.dumps(resp)[:300]}")
        time.sleep(interval)
    raise OmniHumanError(f"timed out after {timeout}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="public image URL")
    parser.add_argument("--audio", required=True, help="public audio URL (<60s)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--resolution", type=int, default=720, choices=[720, 1080])
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    try:
        client = _client()
        task_id = submit(client, image_url=args.image, audio_url=args.audio,
                         prompt=args.prompt, seed=args.seed, resolution=args.resolution)
        print(f"submitted task_id={task_id}", flush=True)
        video_url = poll(client, task_id, args.timeout)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(video_url, timeout=300) as r:
            out.write_bytes(r.read())
        print(f"wrote {out} ({out.stat().st_size} bytes)")
        return 0
    except OmniHumanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
