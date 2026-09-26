#!/usr/bin/env python3
"""声音复刻固化：把一条已验收的演绎参考音频克隆成专属 Speaker ID。

走新版控制台 API（X-Api-Key 鉴权，与 seed-tts 合成同一把 key，
不需要旧版 AppID/Access Token）：

  训练：POST https://openspeech.bytedance.com/api/v3/tts/voice_clone
  查询：POST https://openspeech.bytedance.com/api/v3/tts/get_voice
        （status: 0 NotFound / 1 Training / 2 Success / 3 Failed / 4 Active，
         2 或 4 可调用合成）
  合成：复用 seedtts_say.synthesize（V3 HTTP 单向流式），resource id 依次实测。

官方文档：
  音色训练HTTP https://docs.volcengine.com/docs/DoubaoVoice/tone-training-http
  音色查询HTTP https://docs.volcengine.com/docs/6561/2535742

注意（官方计费口径）：首次调用合成接口即视为"转正"并收取音色槽位费，
确认试听满意前不要拿克隆音色跑正式批量合成。

Usage:
  set -a && source dula-story/.env.speech && set +a
  python clone_voice.py --ref <wav> --speaker-id leixiao_zhansun_v1 \
      --name "雷晓·战损" --verify-text "白……岚……部……长……" --out <dir>

Exit codes: 0 成功 / 2 凭证缺失 / 3 鉴权或服务未开通（打印控制台补救指引）/ 1 其他错误。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[2]
SEEDTTS_TOOLS = WORKSPACE_ROOT / "dula-story" / "episodes" / "yuki_bento_battle" / "tools"
sys.path.insert(0, str(SEEDTTS_TOOLS))

from seedtts_say import SeedTTSError, get_api_key, synthesize  # noqa: E402

CLONED_PATH = SCRIPT_DIR.parent / "references" / "cloned_voices.json"

CLONE_URL = "https://openspeech.bytedance.com/api/v3/tts/voice_clone"
STATUS_URL = "https://openspeech.bytedance.com/api/v3/tts/get_voice"
# 合成 resource 候选，按实测优先级排列（首个可用值会记入 cloned_voices.json）
RESOURCE_CANDIDATES = ["seed-tts-2.0", "seed-icl-2.0"]

POLL_INTERVAL = 10
POLL_TIMEOUT = 600  # 官方口径训练一般 1 分钟内，留足余量

STATUS_LABELS = {0: "NotFound", 1: "Training", 2: "Success", 3: "Failed", 4: "Active"}

# 官方命名规范：8~256 字符，字母开头，仅数字/字母/-/_，
# 不可用官方前缀（S_/ICL_/MIX_/DiT_/BV、两字母+下划线、行星前缀）或 _tob/_bigtts 等后缀
OFFICIAL_PATTERN = re.compile(
    r"^((?i:S_|ICL_|MIX_|DiT_|BV)|[a-z]{2}_"
    r"|(?i:(wvae|moon|mercury|venus|earth|mars|jupiter|saturn|uranus|neptune|pluto|umm)_)).*"
    r"|.*_(?i:bigtts|bigtts_cc|tob|cs_tob|streaming)$"
    r"|^[^a-zA-Z]|.*[-_]$|^.{0,7}$|^.{257,}$|.*[^a-zA-Z0-9_-].*"
)

REMEDY_GRANT = """\
服务未开通（不是 key 问题，X-Api-Key 鉴权已通过）。去语音技术新版控制台：
1. 开通管理：开通「豆包声音复刻模型2.0」，
   并单独开通「音色服务」的后付费音色（报错里的 volc.megatts.timbre 就是它，
   官方口径：后付费音色需勾选声音复刻模型2.0 + 音色服务，并手动开通后付费音色服务）
   https://console.volcengine.com/speech/new/setting/activate?projectName=default
2. 开通后直接重跑本脚本即可，无需改任何凭证。"""

REMEDY_AUTH = """\
API Key 不被接受。检查：
1. API Key 管理：确认 VOLC_SPEECH_API_KEY 与开通服务的项目一致（各项目资源隔离）
   https://console.volcengine.com/speech/new/setting/apikeys?projectName=default
2. 若你的应用建在旧版控制台，v3 接口不认 X-Api-Key，需走旧接口
   （/api/v1/mega_tts/audio/upload + Bearer Token），把控制台使用FAQ-Q1 里的
   AppID / Access Token 补进 dula-story/.env.speech：
   VOLC_SPEECH_APP_ID=... / VOLC_SPEECH_ACCESS_TOKEN=..."""


class CloneError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


def _post_json(url: str, api_key: str, body: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "X-Api-Request-Id": str(uuid.uuid4()),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code == 403 and "not granted" in detail:
            raise CloneError(f"HTTP 403: {detail}\n\n{REMEDY_GRANT}", exit_code=3) from exc
        if exc.code in (401, 403):
            raise CloneError(f"HTTP {exc.code}: {detail}\n\n{REMEDY_AUTH}", exit_code=3) from exc
        raise CloneError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CloneError(f"网络错误：{exc.reason}") from exc


def upload_training(api_key: str, speaker_id: str, ref_path: Path,
                    language: int, text: str | None, demo_text: str | None) -> dict:
    audio_b64 = base64.b64encode(ref_path.read_bytes()).decode("ascii")
    body: dict = {
        # 后付费自定义音色：speaker_id 固定传 "custom_speaker_id"
        "speaker_id": "custom_speaker_id",
        "custom_speaker_id": speaker_id,
        "audio": {"data": audio_b64, "format": ref_path.suffix.lstrip(".").lower()},
        "language": language,
    }
    if text:
        body["text"] = text
    if demo_text:
        body["extra_params"] = {"demo_text": demo_text}
    resp = _post_json(CLONE_URL, api_key, body)
    if resp.get("code", 0) not in (0, None):
        raise CloneError(f"训练提交失败 code={resp.get('code')}: {resp.get('message')}")
    return resp


def query_status(api_key: str, speaker_id: str) -> dict:
    return _post_json(STATUS_URL, api_key, {
        "speaker_id": "custom_speaker_id",
        "custom_speaker_id": speaker_id,
    })


def wait_until_ready(api_key: str, speaker_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT
    while True:
        resp = query_status(api_key, speaker_id)
        status = resp.get("status", 0)
        label = STATUS_LABELS.get(status, str(status))
        print(f"  训练状态: {label}（{POLL_INTERVAL}s 后重查）")
        if status in (2, 4):
            return resp
        if status == 3:
            raise CloneError(f"训练失败：{resp.get('message', '(无失败说明)')}")
        if time.time() > deadline:
            raise CloneError(f"等待训练超时（{POLL_TIMEOUT}s），最后状态 {label}，"
                             f"可稍后单独跑状态查询确认")
        time.sleep(POLL_INTERVAL)


def verify_synthesis(api_key: str, speaker_id: str, text: str, out_dir: Path) -> tuple[Path, str]:
    """依次试 resource 候选，返回 (输出路径, 实测可用 resource_id)。"""
    errors: list[str] = []
    for resource_id in RESOURCE_CANDIDATES:
        out_path = out_dir / f"{speaker_id}__verify_{resource_id.replace('.', '_')}.mp3"
        try:
            synthesize(text, speaker_id, out_path, resource_id=resource_id)
            return out_path, resource_id
        except SeedTTSError as exc:
            errors.append(f"{resource_id}: {exc}")
            print(f"  resource {resource_id} 不可用：{exc}")
    raise CloneError("所有 resource 候选都合成失败：\n" + "\n".join(errors))


def f0_compare(ref_path: Path, out_path: Path) -> str:
    """用 librosa 对参考与克隆输出做 F0 中位数对比（librosa 不在环境则跳过）。"""
    try:
        import librosa
        import numpy as np
    except ImportError:
        return "(librosa/numpy 不可用，跳过 F0 对比)"

    def median_f0(path: Path) -> float | None:
        y, sr = librosa.load(str(path), sr=None, mono=True)
        f0, _, _ = librosa.pyin(
            y, sr=sr, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C6")
        )
        voiced = f0[~np.isnan(f0)]
        return float(np.median(voiced)) if len(voiced) else None

    ref_f0 = median_f0(ref_path)
    out_f0 = median_f0(out_path)
    if ref_f0 is None or out_f0 is None:
        return f"(F0 提取失败：ref={ref_f0}, out={out_f0})"
    ratio = out_f0 / ref_f0
    return (f"参考 F0 中位数 {ref_f0:.1f} Hz，克隆输出 {out_f0:.1f} Hz，"
            f"比值 {ratio:.2f}（0.9~1.1 视为同音高区间）")


def append_registry(entry: dict) -> None:
    CLONED_PATH.parent.mkdir(parents=True, exist_ok=True)
    registry: list[dict] = []
    if CLONED_PATH.is_file():
        registry = json.loads(CLONED_PATH.read_text(encoding="utf-8"))
    registry = [e for e in registry if e.get("speaker_id") != entry["speaker_id"]]
    registry.append(entry)
    CLONED_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="声音复刻固化：参考音频 → 专属 Speaker ID")
    parser.add_argument("--ref", type=Path, required=True, help="已验收的参考音频（wav/mp3，≤10MB）")
    parser.add_argument("--speaker-id", required=True, help="自定义音色 ID（字母开头，8~256 位）")
    parser.add_argument("--name", default="", help="备注名（如 雷晓·战损）")
    parser.add_argument("--language", type=int, default=0, help="语种，0=中文（默认）")
    parser.add_argument("--text", default=None, help="参考音频对应文本（WER 校验用，可选）")
    parser.add_argument("--demo-text", default=None, help="训练试听文本（4~300 字，可选）")
    parser.add_argument("--verify-text", default="白……岚……部……长……",
                        help="训练成功后的合成验证台词")
    parser.add_argument("--out", type=Path, required=True, help="验证音频输出目录")
    parser.add_argument("--skip-verify", action="store_true", help="只训练，不合成验证")
    args = parser.parse_args()

    if OFFICIAL_PATTERN.match(args.speaker_id):
        print(f"ERROR: speaker_id {args.speaker_id!r} 不符合官方命名规范"
              f"（字母开头、8~256 位、不能撞官方前缀/后缀）", file=sys.stderr)
        return 1
    if not args.ref.is_file():
        print(f"ERROR: 参考音频不存在：{args.ref}", file=sys.stderr)
        return 1
    if args.ref.stat().st_size > 10 * 1024 * 1024:
        print("ERROR: 参考音频超过 10MB 上限", file=sys.stderr)
        return 1
    api_key = get_api_key()
    if not api_key:
        print("ERROR: VOLC_SPEECH_API_KEY 未设置。先执行：\n"
              "  set -a && source dula-story/.env.speech && set +a", file=sys.stderr)
        return 2

    try:
        print(f"== 1/3 提交训练（{args.ref.name} → {args.speaker_id}）==")
        resp = upload_training(api_key, args.speaker_id, args.ref,
                               args.language, args.text, args.demo_text)
        print(f"  已提交，剩余训练次数: {resp.get('available_training_times', '?')}")

        print("== 2/3 轮询训练状态 ==")
        final = wait_until_ready(api_key, args.speaker_id)

        resource_id = None
        f0_report = None
        if not args.skip_verify:
            print("== 3/3 合成验证 ==")
            args.out.mkdir(parents=True, exist_ok=True)
            out_path, resource_id = verify_synthesis(
                api_key, args.speaker_id, args.verify_text, args.out
            )
            print(f"  合成成功（resource={resource_id}）：{out_path}")
            f0_report = f0_compare(args.ref, out_path)
            print(f"  F0 对比：{f0_report}")

        now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        append_registry({
            "speaker_id": args.speaker_id,
            "name": args.name,
            "ref_path": str(args.ref),
            "created_at": now,
            "resource_id": resource_id,
            "language": args.language,
            "available_training_times": final.get("available_training_times"),
        })
        print(f"\n已登记 {CLONED_PATH}")
        print(f"voice_config.json 写法：\"speaker\": \"{args.speaker_id}\""
              + (f"，\"resourceId\": \"{resource_id}\"" if resource_id else
                 "（resourceId 待合成验证后补充）"))
        return 0
    except CloneError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
