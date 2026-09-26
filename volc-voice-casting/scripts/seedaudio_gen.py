#!/usr/bin/env python3
"""Generate pure-SFX / pure-BGM stems via Volcano Seed-Audio 1.0 (E04).

Endpoint: POST https://openspeech.bytedance.com/api/v3/tts/create
(non-streaming, base64 audio in the JSON response, max 120 s per call).
Auth: X-Api-Key = the SPEECH console key (env VOLC_SPEECH_API_KEY) — the same
key family as seed-tts-2.0, NOT the ARK key (Ark tasks endpoint 404s for
seed-audio on accounts without the invite).

Deliberately used in single-element mode only (pure ambience / pure music):
the all-in-one "dialogue+SFX+BGM" mode would break the episode's per-bus
mixing and lip-sync pipeline.

Usage:
  seedaudio_gen.py --prompt "生成一段60秒..." --out out.wav [--timeout 300]

Run with the workspace venv:  dula-story/.venv/Scripts/python.exe
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API_URL = "https://openspeech.bytedance.com/api/v3/tts/create"
MODEL = "seed-audio-1.0"
API_KEY_ENV = "VOLC_SPEECH_API_KEY"


class SeedAudioError(RuntimeError):
    pass


def generate(prompt: str, out_path: Path, *, audio_format: str = "wav",
             sample_rate: int = 48000, timeout: float = 300.0) -> float:
    """Generate one audio clip; returns the billed original_duration (s)."""
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise SeedAudioError(f"{API_KEY_ENV} is not set in this process")
    payload = {
        "model": MODEL,
        "text_prompt": prompt,
        "audio_config": {"format": audio_format, "sample_rate": sample_rate},
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-Api-Key": api_key,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")[:600]
        raise SeedAudioError(f"HTTP {exc.code}: {text}") from exc
    code = body.get("code")
    if code not in (None, 0, 20000000):
        raise SeedAudioError(f"API error code={code}: {body.get('message')}")
    audio = body.get("audio")
    if not audio:
        raise SeedAudioError(f"response contained no audio: {str(body)[:300]}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(audio))
    return float(body.get("original_duration") or body.get("duration") or 0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate audio via Seed-Audio 1.0.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--format", default="wav")
    parser.add_argument("--sample-rate", type=int, default=48000)
    args = parser.parse_args()
    if not os.environ.get(API_KEY_ENV):
        print(f"ERROR: {API_KEY_ENV} is not set.", file=sys.stderr)
        return 2
    try:
        duration = generate(args.prompt, Path(args.out),
                            audio_format=args.format, sample_rate=args.sample_rate)
    except SeedAudioError as exc:
        print(f"ERROR: generation failed: {exc}", file=sys.stderr)
        return 1
    size = Path(args.out).stat().st_size
    print(f"wrote {args.out} ({size} bytes, billed {duration}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
