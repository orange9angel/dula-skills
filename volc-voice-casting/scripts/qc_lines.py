#!/usr/bin/env python3
"""人声验收自动化（QC）：让"监制不逐条听"成为制度。

对每条正式音频做机器可判的检查，全绿直接入库进混音，不打扰监制：
- 时长 vs 窗口：超窗 >0.2s ❌，临界 ±0.2s ⚠️，其余 ✅（无窗口只报时长）
- 削波：峰值 >0.99 ❌；过低电平：峰值 <0.15 ⚠️（提醒混音补偿）
- F0 中位数与 P10-P90 范围：仅报告，不判定
- dialogue：faster_whisper 转写 → 拼音级比对（去声调拼音序列相似度
  ≥85% ✅ / 60-85% ⚠️ / <60% ❌）——必须比拼音不能比汉字：
  战损气声台词转写会出同音字（「白岚部长」→「白蓝不长」），发音其实是对的
- nonverbal（嘶吼/喘息等）：非静音占比 >50% ✅，否则 ⚠️

退出码：全 ✅ = 0；有 ⚠️ = 1；有 ❌ = 2。

Usage:
  set -a && source dula-story/.env.speech && set +a   # 不需要 key，本地模型
  python qc_lines.py \
      --expect "白岚部长@dula-story/.../fight_01_leixiao.mp3" \
      --expect "学生会命令九章今晚回收@dula-story/.../fight_02_bailan.mp3" \
      --manifest qc.json --out-report qc_report.md

manifest 格式：[{"file": ..., "expect_text": null|str,
                 "window_s": null|float, "kind": "dialogue"|"nonverbal"}]

依赖：faster_whisper、librosa（venv 已装）、pypinyin（缺失时 pip install；
装不上则退化为去标点字符重合率 + 人工复核标记）。
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

try:
    from pypinyin import Style, lazy_pinyin
    HAS_PINYIN = True
except ImportError:
    HAS_PINYIN = False

# 判定阈值（SKILL.md「自动化验收纪律」的指标口径与这里保持一致）
WINDOW_TOLERANCE = 0.2      # 时长临界 ±s
CLIP_PEAK = 0.99            # 削波峰值
LOW_PEAK = 0.15             # 过低电平峰值
PINYIN_OK = 0.85            # 拼音重合率 ✅ 下限
PINYIN_WARN = 0.60          # ⚠️ 下限
NONSILENT_OK = 0.50         # nonverbal 非静音占比 ✅ 下限

VERDICT_ORDER = {"✅": 0, "⚠️": 1, "❌": 2}

_WHISPER_MODEL = None


def _whisper(model_size: str):
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        _WHISPER_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _WHISPER_MODEL


def load_audio(path: Path):
    import librosa
    y, sr = librosa.load(str(path), sr=None, mono=True)
    return y, sr


def check_duration(dur: float, window: float | None) -> tuple[str, str]:
    if window is None:
        return "✅", f"{dur:.2f}s（无窗口）"
    over = dur - window
    if over > WINDOW_TOLERANCE:
        return "❌", f"{dur:.2f}s 超窗 {over:+.2f}s"
    if over >= -WINDOW_TOLERANCE:
        return "⚠️", f"{dur:.2f}s 临界（{over:+.2f}s / 窗 {window:.2f}s）"
    return "✅", f"{dur:.2f}s / 窗 {window:.2f}s"


def check_peak(peak: float) -> tuple[str, str]:
    if peak > CLIP_PEAK:
        return "❌", f"峰值 {peak:.3f} 削波"
    if peak < LOW_PEAK:
        return "⚠️", f"峰值 {peak:.3f} 电平过低，混音需补偿"
    return "✅", f"峰值 {peak:.3f}"


def f0_stats(y, sr) -> str:
    import librosa
    import numpy as np
    f0, _, _ = librosa.pyin(y, sr=sr, fmin=librosa.note_to_hz("C2"),
                            fmax=librosa.note_to_hz("C6"))
    voiced = f0[~np.isnan(f0)]
    if len(voiced) < 5:
        return "（有效帧不足，无法提取）"
    p10, p90 = np.percentile(voiced, [10, 90])
    return f"{float(np.median(voiced)):.1f} Hz（P10 {p10:.0f} ~ P90 {p90:.0f}）"


def _to_pinyin(text: str) -> list[str]:
    """去标点、去声调，只保留汉字的拼音音节序列。"""
    han = re.findall(r"[一-鿿]", text)
    return lazy_pinyin("".join(han), style=Style.NORMAL)


def _to_chars(text: str) -> list[str]:
    return re.findall(r"[一-鿿a-zA-Z0-9]", text)


def pinyin_similarity(expect: str, actual: str) -> tuple[float, str]:
    """返回 (相似度, 比对方式说明)。编辑距离基于拼音音节序列。"""
    if HAS_PINYIN:
        a, b = _to_pinyin(expect), _to_pinyin(actual)
        mode = "拼音"
    else:
        a, b = _to_chars(expect), _to_chars(actual)
        mode = "字符（pypinyin 缺失，需人工复核）"
    if not a or not b:
        return 0.0, mode
    ratio = difflib.SequenceMatcher(a=a, b=b).ratio()
    return ratio, mode


def check_dialogue(path: Path, expect: str, model_size: str) -> tuple[str, str, str, str]:
    """返回 (判定, 说明, 转写文本, 比对方式)。"""
    model = _whisper(model_size)
    segments, _ = model.transcribe(str(path), language="zh")
    transcript = "".join(seg.text for seg in segments).strip()
    if not transcript:
        return "❌", "转写为空（可能无人声）", transcript, "-"
    ratio, mode = pinyin_similarity(expect, transcript)
    if ratio >= PINYIN_OK:
        verdict = "✅"
    elif ratio >= PINYIN_WARN:
        verdict = "⚠️"
    else:
        verdict = "❌"
    return verdict, f"{mode}重合率 {ratio:.0%}", transcript, mode


def check_nonverbal(y, sr) -> tuple[str, str]:
    import librosa
    intervals = librosa.effects.split(y, top_db=30)
    voiced = sum(end - start for start, end in intervals) / max(len(y), 1)
    if voiced > NONSILENT_OK:
        return "✅", f"非静音占比 {voiced:.0%}"
    return "⚠️", f"非静音占比 {voiced:.0%}（≤50%）"


def qc_item(item: dict, model_size: str) -> dict:
    path = Path(item["file"])
    kind = item.get("kind", "dialogue")
    expect = item.get("expect_text")
    window = item.get("window_s")
    result: dict = {"file": str(path), "kind": kind, "expect": expect,
                    "transcript": "", "checks": [], "verdict": "✅"}
    if not path.is_file():
        result["checks"].append(("❌", f"文件不存在：{path}"))
        result["verdict"] = "❌"
        return result

    y, sr = load_audio(path)
    dur = len(y) / sr
    import numpy as np
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    result["duration"] = dur
    result["peak"] = peak
    result["f0"] = f0_stats(y, sr)

    result["checks"].append(check_duration(dur, window))
    result["checks"].append(check_peak(peak))
    if kind == "dialogue":
        verdict, note, transcript, _mode = check_dialogue(path, expect or "", model_size)
        result["transcript"] = transcript
        result["checks"].append((verdict, note))
    else:
        result["checks"].append(check_nonverbal(y, sr))

    result["verdict"] = max((v for v, _ in result["checks"]),
                            key=lambda v: VERDICT_ORDER[v])
    return result


def render_report(results: list[dict]) -> str:
    lines = ["# 人声验收 QC 报告", ""]
    lines.append("| 文件 | 类型 | 时长 | 峰值 | F0 中位数(P10-P90) | 转写 | 检查明细 | 判定 |")
    lines.append("|------|------|------|------|---------------------|------|----------|------|")
    for r in results:
        if "duration" not in r:
            detail = "；".join(n for _, n in r["checks"])
            lines.append(f"| {Path(r['file']).name} | {r['kind']} | - | - | - | - | {detail} | {r['verdict']} |")
            continue
        detail = "<br>".join(f"{v} {n}" for v, n in r["checks"])
        transcript = r["transcript"] or "-"
        lines.append(
            f"| {Path(r['file']).name} | {r['kind']} | {r['duration']:.2f}s "
            f"| {r['peak']:.3f} | {r['f0']} | {transcript} | {detail} | {r['verdict']} |"
        )
    counts = {"✅": 0, "⚠️": 0, "❌": 0}
    for r in results:
        counts[r["verdict"]] += 1
    lines += ["",
              f"汇总：✅ {counts['✅']} 条 / ⚠️ {counts['⚠️']} 条 / ❌ {counts['❌']} 条",
              "",
              "纪律：全 ✅ 直接入库进混音；有 ❌ 由 AI 重生（换音色/换演绎）直到转绿；"
              "仅「戏感二选一」或「连续 3 次重生仍红」才上报监制。"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="人声验收自动化（QC）")
    parser.add_argument("--expect", action="append", default=[],
                        help='"台词@文件路径"，可多次（kind=dialogue）')
    parser.add_argument("--manifest", type=Path, default=None,
                        help="qc.json：[{file, expect_text, window_s, kind}]")
    parser.add_argument("--window", type=float, default=None,
                        help="--expect 形式的统一窗口秒数")
    parser.add_argument("--whisper-model", default="small", help="faster_whisper 模型，默认 small")
    parser.add_argument("--out-report", type=Path, required=True, help="markdown 报告输出路径")
    args = parser.parse_args()

    items: list[dict] = []
    for spec in args.expect:
        if "@" not in spec:
            print(f"ERROR: --expect 格式应为 台词@文件：{spec!r}", file=sys.stderr)
            return 2
        text, _, file = spec.rpartition("@")
        items.append({"file": file, "expect_text": text,
                      "window_s": args.window, "kind": "dialogue"})
    if args.manifest:
        if not args.manifest.is_file():
            print(f"ERROR: manifest 不存在：{args.manifest}", file=sys.stderr)
            return 2
        items.extend(json.loads(args.manifest.read_text(encoding="utf-8")))
    if not items:
        print("ERROR: 需要 --expect 或 --manifest", file=sys.stderr)
        return 2
    if not HAS_PINYIN:
        print("警告：pypinyin 未安装，拼音比对退化为字符重合率 + 人工复核标记。"
              "安装：dula-story/.venv/Scripts/python.exe -m pip install pypinyin",
              file=sys.stderr)

    results = [qc_item(item, args.whisper_model) for item in items]
    report = render_report(results)
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\n报告已写入 {args.out_report}")

    worst = max((VERDICT_ORDER[r["verdict"]] for r in results), default=0)
    return worst


if __name__ == "__main__":
    sys.exit(main())
