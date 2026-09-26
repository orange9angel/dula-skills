#!/usr/bin/env python3
"""Seed-Audio 参考音频锁音色：用验收过的演绎音频当参考，逐次锁定角色声线。

替代声音复刻音色槽位（138 元/个）的低成本路线：每次生成把参考音频一起
上传（最多 3 条、单条 ≤30s、≤10MB，wav/mp3/pcm/ogg_opus），prompt 里用
@音频N（N 从 1 开始，与 --ref 顺序严格对应）引用。

接口（官方文档 docs.volcengine.com/docs/6561/2550782）：
  POST https://openspeech.bytedance.com/api/v3/tts/create
  body: model=seed-audio-1.0、text_prompt（@音频N 引用）、
        references=[{audio_data: base64}（与 speaker/audio_url 互斥）]、
        audio_config（format/sample_rate，另有 speech_rate/loudness_rate/
        pitch_rate 可调）
  鉴权 X-Api-Key（VOLC_SPEECH_API_KEY），与 seed-tts 同一把。

Usage:
  set -a && source dula-story/.env.speech && set +a
  python seedaudio_acted.py \
    --prompt "生成一段4秒纯人声台词录音，无音乐无音效无背景声：\
参考@音频1里的重伤少年，同样嘶哑气弱地念出：明……天……放……学……" \
    --ref S1_acted_v1.wav --out out.wav

Exit codes: 0 成功 / 2 凭证缺失 / 1 生成失败（打印服务端原始报错帮助迭代）。
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

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[2]
SEEDAUDIO_TOOLS = WORKSPACE_ROOT / "dula-skills" / "volc-voice-casting" / "scripts"
sys.path.insert(0, str(SEEDAUDIO_TOOLS))

from seedaudio_gen import API_KEY_ENV, API_URL, MODEL, SeedAudioError  # noqa: E402

MAX_REFS = 3
MAX_REF_BYTES = 10 * 1024 * 1024
MAX_REF_SECONDS = 30.0
SUPPORTED_REF_FORMATS = {"wav", "mp3", "pcm", "ogg_opus", "ogg"}


def _ref_duration(path: Path) -> float | None:
    try:
        import librosa
        return float(librosa.get_duration(path=str(path)))
    except Exception:
        return None  # 测不出不阻塞，交给服务端校验


def build_references(ref_paths: list[Path]) -> list[dict]:
    refs: list[dict] = []
    for path in ref_paths:
        if not path.is_file():
            raise SeedAudioError(f"参考音频不存在：{path}")
        if path.stat().st_size > MAX_REF_BYTES:
            raise SeedAudioError(f"参考音频超过 10MB：{path}")
        fmt = path.suffix.lstrip(".").lower()
        if fmt not in SUPPORTED_REF_FORMATS:
            raise SeedAudioError(f"参考音频格式不支持（wav/mp3/pcm/ogg_opus）：{path}")
        dur = _ref_duration(path)
        if dur is not None and dur > MAX_REF_SECONDS:
            raise SeedAudioError(f"参考音频超过 30s（{dur:.1f}s）：{path}")
        refs.append({"audio_data": base64.b64encode(path.read_bytes()).decode("ascii")})
    return refs


def generate_acted(prompt: str, ref_paths: list[Path], out_path: Path, *,
                   audio_format: str = "wav", sample_rate: int = 48000,
                   timeout: float = 300.0) -> float:
    """带参考音频生成一条演绎音频；返回计费 original_duration（s）。"""
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise SeedAudioError(f"{API_KEY_ENV} is not set in this process")
    payload: dict = {
        "model": MODEL,
        "text_prompt": prompt,
        "audio_config": {"format": audio_format, "sample_rate": sample_rate},
    }
    if ref_paths:
        payload["references"] = build_references(ref_paths)
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
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
        text = exc.read().decode("utf-8", errors="replace")[:800]
        raise SeedAudioError(f"HTTP {exc.code}: {text}") from exc
    code = body.get("code")
    if code not in (None, 0, 20000000):
        # 打印原始报错体，字段名迭代时靠它反推
        raise SeedAudioError(f"API error: {json.dumps(body, ensure_ascii=False)[:800]}")
    audio = body.get("audio")
    if not audio:
        raise SeedAudioError(f"response contained no audio: {str(body)[:500]}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(audio))
    return float(body.get("original_duration") or body.get("duration") or 0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed-Audio 参考音频锁音色生成")
    parser.add_argument("--prompt", required=True,
                        help="提示词；用 @音频1/@音频2... 引用 --ref 对应位置的参考音频")
    parser.add_argument("--ref", type=Path, action="append", default=[],
                        help="参考音频（可多个，最多 3 条，单条 ≤30s ≤10MB）")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--format", default="wav")
    parser.add_argument("--sample-rate", type=int, default=48000)
    args = parser.parse_args()

    if len(args.ref) > MAX_REFS:
        print(f"ERROR: 参考音频最多 {MAX_REFS} 条", file=sys.stderr)
        return 1
    if not os.environ.get(API_KEY_ENV):
        print(f"ERROR: {API_KEY_ENV} 未设置。先 set -a && source dula-story/.env.speech && set +a",
              file=sys.stderr)
        return 2
    try:
        duration = generate_acted(args.prompt, args.ref, args.out,
                                  audio_format=args.format, sample_rate=args.sample_rate)
    except SeedAudioError as exc:
        print(f"ERROR: 生成失败：{exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes, billed {duration}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
