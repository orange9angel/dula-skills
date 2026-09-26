#!/usr/bin/env python3
"""批量试听 seed-tts-2.0 音色（角色选声用）。

复用 skill 内正本 seedtts_say.py 的 synthesize()（V3 HTTP
单向流式合成，VOLC_SPEECH_API_KEY 来自 dula-story/.env.speech）。

音色来源二选一：
  --voices v1,v2,...          显式指定 VoiceType 列表
  --category 演绎 --gender 男  从 references/voice_catalog.json 筛选（先跑 build_voice_catalog.py）

台词来源二选一：
  --text "台词" [--text ...]              直接给台词（可多条）
  --episode <path> --character <名>       从 script.story 解析该角色台词行
                                          （[Character]{Voice:emotion}台词 格式，逐行窗口取 SRT 时间轴）

403 "requested resource not granted"（未解锁音色）不中断，记入结尾待解锁清单。
同名覆盖、单条失败继续。

Usage:
  set -a && source dula-story/.env.speech && set +a
  python audition_voices.py --text "台词" --voices zh_male_xxx,zh_male_yyy \
      --window 4.8 --out <dir>
  python audition_voices.py --episode dula-story/episodes/<ep> --character 角色名 \
      --category 演绎 --gender 男 --emotion sad --emotion-scale 2 --out <dir>

Exit codes: 0 全部成功（含已跳过未解锁）/ 2 凭证缺失 / 1 参数或运行错误。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[2]  # scripts -> volc-voice-casting -> dula-skills -> root
SEEDTTS_TOOLS = WORKSPACE_ROOT / "dula-skills" / "volc-voice-casting" / "scripts"
sys.path.insert(0, str(SEEDTTS_TOOLS))

from seedtts_say import SeedTTSError, get_api_key, synthesize  # noqa: E402

CATALOG_PATH = SCRIPT_DIR.parent / "references" / "voice_catalog.json"
CONSOLE_URL = "https://console.volcengine.com/speech/new/setting/activate?projectName=default"

TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)
DIALOGUE_RE = re.compile(r"^\[([^\]]+)\](.*)$")
TAG_RE = re.compile(r"\{[^}]*\}")
VOICE_TAG_RE = re.compile(r"\{Voice:([^}|]+)")


def _hms(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_story_lines(episode_dir: Path, character: str) -> list[dict]:
    """从 script.story 提取指定角色的台词行（含 SRT 窗口与 Voice 标签情感）。"""
    story_path = episode_dir / "script.story"
    if not story_path.is_file():
        raise FileNotFoundError(f"找不到剧本：{story_path}")
    lines: list[dict] = []
    window: float | None = None
    for raw in story_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        ts = TIMESTAMP_RE.search(line)
        if ts:
            window = _hms(*ts.group(5, 6, 7, 8)) - _hms(*ts.group(1, 2, 3, 4))
            continue
        m = DIALOGUE_RE.match(line)
        if not m or m.group(1) != character:
            continue
        rest = m.group(2)
        voice = VOICE_TAG_RE.search(rest)
        text = TAG_RE.sub("", rest).strip()
        if not text:
            continue
        lines.append({
            "text": text,
            "window": window,
            "emotion": voice.group(1).strip() if voice else None,
        })
    return lines


def load_catalog_voices(category: str | None, gender: str | None) -> list[dict]:
    if not CATALOG_PATH.is_file():
        raise FileNotFoundError(
            f"音色目录不存在：{CATALOG_PATH}\n先运行 build_voice_catalog.py 生成。"
        )
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [
        sp for sp in catalog.get("speakers", [])
        if (not category or sp.get("category") == category)
        and (not gender or sp.get("Gender") == gender)
    ]


def measure_duration(path: Path) -> float | None:
    """优先 ffprobe（PATH 里有），wav 兜底用 wave 模块。"""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            return float(out.stdout.strip())
        except (ValueError, subprocess.SubprocessError):
            pass
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        except wave.Error:
            pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="seed-tts-2.0 批量试听（角色选声）")
    parser.add_argument("--text", action="append", default=[], help="台词，可多次")
    parser.add_argument("--episode", type=Path, default=None, help="episode 目录（读 script.story）")
    parser.add_argument("--character", default=None, help="从剧本提取该角色的台词")
    parser.add_argument("--voices", default=None, help="逗号分隔的 VoiceType 列表")
    parser.add_argument("--category", default=None, choices=["演绎", "资讯", "其他"])
    parser.add_argument("--gender", default=None, help="配合 --category 筛选，如 男/女")
    parser.add_argument("--emotion", default=None, help="统一情感标签（被剧本 Voice 标签覆盖）")
    parser.add_argument("--emotion-scale", type=int, default=None, choices=range(1, 6),
                        help="情感强度 1-5（默认 3，弱档 2 最稳）")
    parser.add_argument("--window", type=float, default=None, help="目标时长秒（剧本模式默认逐行取 SRT 窗口）")
    parser.add_argument("--out", type=Path, required=True, help="试听输出目录")
    args = parser.parse_args()

    # 台词来源
    items: list[dict] = []
    if args.episode and args.character:
        try:
            items = parse_story_lines(args.episode, args.character)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if not items:
            print(f"ERROR: 剧本中找不到角色 {args.character} 的台词", file=sys.stderr)
            return 1
    elif args.text:
        items = [{"text": t, "window": None, "emotion": None} for t in args.text]
    else:
        print("ERROR: 需要 --text 或 --episode + --character", file=sys.stderr)
        return 1

    # 音色来源
    if args.voices:
        voices = [{"VoiceType": v.strip(), "Name": ""}
                  for v in args.voices.split(",") if v.strip()]
    elif args.category or args.gender:
        try:
            voices = load_catalog_voices(args.category, args.gender)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if not voices:
            print("ERROR: catalog 中无匹配音色", file=sys.stderr)
            return 1
    else:
        print("ERROR: 需要 --voices 或 --category/--gender", file=sys.stderr)
        return 1

    if not get_api_key():
        print(
            "ERROR: VOLC_SPEECH_API_KEY 未设置。先执行：\n"
            "  set -a && source dula-story/.env.speech && set +a",
            file=sys.stderr,
        )
        return 2

    args.out.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    locked: dict[str, str] = {}  # VoiceType -> Name
    failures: list[str] = []

    for voice in voices:
        vt = voice.get("VoiceType", "?")
        for ti, item in enumerate(items, 1):
            emotion = item["emotion"] or args.emotion
            suffix = f"_{emotion}" if emotion else ""
            out_path = args.out / f"{vt}__t{ti:02d}{suffix}.mp3"
            window = args.window if args.window is not None else item["window"]
            try:
                synthesize(
                    item["text"], vt, out_path,
                    emotion=emotion, emotion_scale=args.emotion_scale,
                )
            except SeedTTSError as exc:
                if exc.code == 403 or "not granted" in str(exc):
                    locked[vt] = voice.get("Name", "")
                    print(f"  [未解锁] {vt}，记入待解锁清单")
                    break  # 该音色后续台词不必再试
                hint = ""
                if "no audio data" in str(exc):
                    hint = "（空成功坑：音色可能不支持该文本语言，返回 200 但零音频）"
                failures.append(f"{vt} × t{ti:02d}: {exc}{hint}")
                print(f"  [失败] {vt} × t{ti:02d}: {exc}{hint}", file=sys.stderr)
                continue
            duration = measure_duration(out_path)
            rows.append({
                "voice": vt, "text": item["text"], "duration": duration,
                "window": window, "emotion": emotion or "-", "path": out_path,
            })
            mark = ""
            if duration is not None and window is not None:
                mark = "✅" if duration <= window else "⚠️"
            print(f"  [完成] {vt} × t{ti:02d} {duration and f'{duration:.2f}s' or '?'} {mark}")

    # markdown 试听报告
    report: list[str] = ["# 试听报告", ""]
    report.append("| 音色 | 台词 | 时长(s) | 窗口(s) | 判定 | emotion | 文件 |")
    report.append("|------|------|---------|---------|------|---------|------|")
    for r in rows:
        dur = f"{r['duration']:.2f}" if r["duration"] is not None else "?"
        win = f"{r['window']:.2f}" if r["window"] is not None else "-"
        if r["duration"] is not None and r["window"] is not None:
            verdict = "✅" if r["duration"] <= r["window"] else "⚠️"
        else:
            verdict = "-"
        text = r["text"] if len(r["text"]) <= 20 else r["text"][:20] + "…"
        report.append(
            f"| {r['voice']} | {text} | {dur} | {win} | {verdict} "
            f"| {r['emotion']} | {r['path']} |"
        )
    if failures:
        report += ["", "## 合成失败（非锁定原因）", ""]
        report += [f"- {f}" for f in failures]
    if locked:
        report += ["", "## 待解锁清单（控制台人工 0 元下单）", ""]
        report.append("以下音色未解锁（403 requested resource not granted），"
                      "解锁无公开 OpenAPI，需到控制台操作：")
        report.append(f"- 入口：语音技术控制台「语音合成2.0」音色广场 {CONSOLE_URL}")
        report.append("- 操作：找到对应音色，「下单支付 0 元」即可解锁，解锁后重跑本脚本")
        report.append("")
        for vt, name in locked.items():
            label = f"{name}（{vt}）" if name else vt
            report.append(f"- [ ] {label}")
    report_text = "\n".join(report)
    print("\n" + report_text)
    (args.out / "report.md").write_text(report_text + "\n", encoding="utf-8")
    print(f"\n报告已写入 {args.out / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
