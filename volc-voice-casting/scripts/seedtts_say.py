#!/usr/bin/env python3
"""Volcano Engine seed-tts-2.0 one-shot synthesis CLI (E04 Cat voice path).

V3 HTTP unidirectional streaming:
  POST https://openspeech.bytedance.com/api/v3/tts/unidirectional
  Headers: X-Api-Key, X-Api-Resource-Id (speaker and resource id must be
  paired, e.g. seed-tts-2.0 + zh_female_vv_uranus_bigtts), X-Api-Request-Id
  (must be unique per call), Content-Type: application/json.
  Response is a line-delimited JSON stream; each line's ``data`` field is a
  base64 audio chunk to concatenate (parsing the whole body as one JSON fails
  with "Extra data").

Access notes (dula-skills/build-character-voice/references/volcano-seedtts.md):
  - The key comes from the speech console (not ARK): env VOLC_SPEECH_API_KEY.
  - "requested resource not granted" (403) = service/voice not unlocked in
    the console; 401 = key problem.
  - Emotion needs emotion + emotion_scale (1-5) + enable_emotion: true.

Usage:
  seedtts_say.py --text "台词" --speaker zh_female_vv_uranus_bigtts \
      --emotion calm --emotion-scale 3 --out out.mp3

Exit codes: 0 ok; 2 missing VOLC_SPEECH_API_KEY; 1 synthesis failure.
Stdlib only (no third-party deps).

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

API_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
DEFAULT_RESOURCE_ID = "seed-tts-2.0"
DEFAULT_FORMAT = "mp3"
DEFAULT_SAMPLE_RATE = 24000
API_KEY_ENV = "VOLC_SPEECH_API_KEY"


class SeedTTSError(RuntimeError):
    """Synthesis failed. ``code`` carries the HTTP status or API code."""

    def __init__(self, message: str, code: int | str | None = None) -> None:
        super().__init__(message)
        self.code = code


def get_api_key() -> str | None:
    return os.environ.get(API_KEY_ENV) or None


def synthesize(
    text: str,
    speaker: str,
    out_path: Path,
    *,
    emotion: str | None = None,
    emotion_scale: int | None = None,
    api_key: str | None = None,
    resource_id: str = DEFAULT_RESOURCE_ID,
    audio_format: str = DEFAULT_FORMAT,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    timeout: float = 60.0,
) -> Path:
    """Synthesize one line and write the encoded audio (mp3) to out_path."""
    api_key = api_key or get_api_key()
    if not api_key:
        raise SeedTTSError(f"{API_KEY_ENV} is not set in this process")

    req_params: dict = {
        "text": text,
        "speaker": speaker,
        "audio_params": {"format": audio_format, "sample_rate": sample_rate},
    }
    if emotion:
        req_params["emotion"] = emotion
        req_params["emotion_scale"] = emotion_scale if emotion_scale else 3
        req_params["enable_emotion"] = True
    payload = {"user": {"uid": "dula-e04-cat"}, "req_params": req_params}
    headers = {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"), headers=headers
    )

    chunks: list[bytes] = []
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_line in response:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # tolerate keep-alive / non-JSON lines
                if event.get("data"):
                    chunks.append(base64.b64decode(event["data"]))
                    continue
                code = event.get("code")
                # 20000000 is Volcano speech's success sentinel on terminal
                # stream frames, not an error.
                if code in (None, 0, 20000000):
                    continue
                raise SeedTTSError(
                    f"API error code={code}: {event.get('message', event)}",
                    code=code,
                )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise SeedTTSError(f"HTTP {exc.code}: {body}", code=exc.code) from exc
    except urllib.error.URLError as exc:
        raise SeedTTSError(f"connection failed: {exc.reason}") from exc

    if not chunks:
        raise SeedTTSError("response contained no audio data")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"".join(chunks))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synthesize one line via Volcano seed-tts-2.0 (V3 HTTP)."
    )
    parser.add_argument("--text", required=True, help="Line to synthesize")
    parser.add_argument("--speaker", required=True, help="e.g. zh_female_vv_uranus_bigtts")
    parser.add_argument("--emotion", help="Optional emotion label (e.g. calm, happy)")
    parser.add_argument(
        "--emotion-scale",
        type=int,
        default=None,
        choices=range(1, 6),
        help="Emotion strength 1-5 (default 3 when --emotion is given)",
    )
    parser.add_argument("--out", required=True, help="Output audio path (mp3)")
    parser.add_argument("--resource-id", default=DEFAULT_RESOURCE_ID)
    parser.add_argument("--format", default=DEFAULT_FORMAT)
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    args = parser.parse_args()

    if not get_api_key():
        print(
            f"ERROR: {API_KEY_ENV} is not set in this process. Get a key from the "
            "Volcano speech console (API Key 管理); it is NOT the ARK key.",
            file=sys.stderr,
        )
        return 2

    try:
        out = synthesize(
            args.text,
            args.speaker,
            Path(args.out),
            emotion=args.emotion,
            emotion_scale=args.emotion_scale,
            resource_id=args.resource_id,
            audio_format=args.format,
            sample_rate=args.sample_rate,
        )
    except SeedTTSError as exc:
        print(f"ERROR: synthesis failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
