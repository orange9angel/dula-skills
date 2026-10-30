#!/usr/bin/env python3
"""唱句逐字对齐（已知歌词）：最终放置的人声分轨 → Whisper 已知文本 DTW → 声学地标单调 DP 吸附。
唱歌里 DTW 字界常偏 0.2-0.4s（字落进换气静音、漏掉换音），只做 ±150ms 起音吸附不够。地标：
  fric  擦/塞擦音爆发起点（4.5kHz 以上 / 150-1500Hz 能量比 >0.8，且 0.15s 内接浊音）
  breath 擦音样噪声后无浊音 = 换气吸气（不作字界；输出 clips[].breaths 供吸气表情）
  voice 浊音起点；step 音高换音（中值 >0.8 半音）；dip 连读能量谷（w/l/d/y 等）
DP：每字可吸附到 DTW 起点 ±0.45s 内一个地标，或保留 DTW（代价 0.35）；声母与地标类型不符加 0.15。
输出与 draw-over-animation/assets/dialogue-face-track.js 的 clips 格式一致（含逐段 gate）。

用法：python align_sung_lyrics.py --stem STEM.wav --lines lines.json --out alignment.json [--model small]
lines.json：[{"cue":"l1","text":"借我一小段旋律","start":30.42,"end":33.40}, ...]（时间=分轨/混音同一零点；
end 要覆盖句尾长音，宁长勿短）。依赖 dula-assets/lib/audio/known_text_alignment.py 与本地 faster-whisper 模型。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import librosa
import numpy as np
from scipy.ndimage import median_filter
from faster_whisper import WhisperModel
from faster_whisper.tokenizer import Tokenizer
from pypinyin import Style, lazy_pinyin

import argparse
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "dula-assets/lib/audio"))
from known_text_alignment import align_text  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stem", type=Path, required=True)
ap.add_argument("--lines", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--model", default="small")
ap.add_argument("--character", default="")
ARGS = ap.parse_args()
STEM, OUT = ARGS.stem.resolve(), ARGS.out
LINES = [(l["cue"], l["text"], l["start"], l["end"]) for l in json.loads(ARGS.lines.read_text(encoding="utf-8"))]
TMP = OUT.parent / "_align_tmp"
TMP.mkdir(parents=True, exist_ok=True)
SR = 16000
HOP = 160  # 10ms

model = WhisperModel(ARGS.model, device="cpu", compute_type="int8", local_files_only=True)
make_tok = lambda: Tokenizer(model.hf_tokenizer, model.model.is_multilingual, task="transcribe", language="zh")


def pcm(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(ss), "-t", str(t)] if ss is not None else []) + \
          ["-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.check_output(cmd), np.float32).astype(np.float64)


def landmarks(x):
    """唱字起点的声学地标（局部秒）：擦/塞擦音爆发起点、浊音起点、音高换音、连读能量谷。
    唱歌里 DTW 字界常偏 0.2-0.4s（R3 实测「哪」落进换气静音），只吸附 ±150ms 不够。"""
    S = np.abs(librosa.stft(x.astype(np.float32), n_fft=512, hop_length=HOP))
    fr = librosa.fft_frequencies(sr=SR, n_fft=512)
    hf, lf = S[fr > 4500].mean(0), S[(fr > 150) & (fr < 1500)].mean(0)
    ratio, lfn = hf / (lf + 1e-6), lf / (lf.max() + 1e-9)
    f0, _, _ = librosa.pyin(x.astype(np.float32), fmin=150, fmax=900, sr=SR, frame_length=1024, hop_length=HOP)
    midi = median_filter(np.where(np.isnan(f0), -1, librosa.hz_to_midi(np.nan_to_num(f0, nan=1.0))), 7)
    out, n = [], len(lfn)
    fric = ratio > .8
    for i in range(1, n - 3):
        if fric[i] and not fric[i - 1] and fric[i:i + 3].all():
            e = i + int(np.argmin(fric[i:])) if not fric[i:].all() else n
            # 擦音后 0.2s 内接浊音才是辅音；否则是换气吸气（表情用 inhale，口型不算字）
            out.append((i / 100, "fric" if lfn[e:e + 15].max(initial=0) > .14 else "breath"))
        if lfn[i] > .3 and lfn[max(0, i - 4):i].max() < .2 and lfn[i] > 2 * lfn[max(0, i - 4):i].min():
            if not any(k == "fric" and 0 < i / 100 - t < .3 for t, k in out):
                out.append((i / 100, "voice"))
        if 5 <= i < n - 5 and (midi[i - 5:i] > 0).all() and (midi[i:i + 5] > 0).all()                 and abs(np.median(midi[i:i + 5]) - np.median(midi[i - 5:i])) > .8:
            out.append((i / 100, "step"))
    sm = np.convolve(lfn, np.ones(5) / 5, mode="same")
    for i in range(6, n - 6):
        if sm[i] == sm[i - 6:i + 7].min() and sm[i] > .12 and min(sm[i - 6:i].max(), sm[i + 1:i + 7].max()) > sm[i] * 1.35:
            out.append((i / 100, "dip"))
    out.sort()
    merged = []
    for t, k in out:  # 同一事件的多条证据合并，优先擦音/浊音起点
        if merged and t - merged[-1][0] < .06:
            if k in ("fric", "voice", "breath") and merged[-1][1] not in ("fric", "voice", "breath"):
                merged[-1] = (t, k)
            continue
        merged.append((t, k))
    return merged


FRIC_INITIALS = {"j", "q", "x", "zh", "ch", "sh", "z", "c", "s", "f", "h"}


def snap_to_landmarks(chars, lm, dur, win=.45, skip=.35, mismatch=.15):
    """单调 DP：每字可吸附到 DTW 起点 ±win 内的一个地标，或不吸附（代价 skip，保留 DTW 起点）。"""
    n, m = len(chars), len(lm)
    INF = 1e9
    best = {(-1, -1): (0.0, None)}  # (字序, 上个地标序) -> (代价, 回溯)
    for i, c in enumerate(chars):
        nxt = {}
        for (pi, pj), (cost, _) in best.items():
            last_t = lm[pj][0] if pj >= 0 else -1
            fr = c["initial"] in FRIC_INITIALS
            cand = [(pj, skip, c["start"])] + [(j, abs(lm[j][0] - c["start"]) + (mismatch if (lm[j][1] == "fric") != fr else 0), lm[j][0])
                                               for j in range(pj + 1, m)
                                               if lm[j][1] != "breath" and abs(lm[j][0] - c["start"]) <= win and lm[j][0] > last_t + .08]
            for j, add, _ in cand:
                key = (i, j)
                if cost + add < nxt.get(key, (INF,))[0]:
                    nxt[key] = (cost + add, (pi, pj, j != pj))
        best = {k: v for k, v in nxt.items()}
        chars[i]["_bp"] = best
    key = min(best, key=lambda k: best[k][0])
    for i in range(n - 1, -1, -1):
        cost, (pi, pj, used) = chars[i]["_bp"][key]
        if used:
            t, kind = lm[key[1]]
            chars[i]["start"], chars[i]["landmark"] = max(0.0, t - .03), kind
        else:
            chars[i]["landmark"] = "dtw"
        key = (pi, pj)
    for c in chars:
        c.pop("_bp", None)
    for i, c in enumerate(chars):
        if i + 1 < len(chars):
            chars[i + 1]["start"] = max(chars[i + 1]["start"], c["start"] + .06)
            c["end"] = chars[i + 1]["start"]
        else:
            c["end"] = max(c["end"], c["start"] + .1)


clips = []
for cue, text, s0, s1 in LINES:
    crop = TMP / f"{cue}_placed.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(s0), "-t", str(s1 - s0), "-i", str(STEM),
                    "-ac", "1", "-ar", str(SR), str(crop)], check=True)
    chars, dur = align_text(model, make_tok, crop, text)
    x = pcm(crop)
    env = np.sqrt(np.mean(x[:len(x) // HOP * HOP].reshape(-1, HOP) ** 2, axis=1) + 1e-12)
    gate = max(.003, float(np.percentile(env, 85)) * .08)
    for c in chars:
        c["dtwStart"], c["dtwEnd"] = c["start"], c["end"]
        c["initial"] = lazy_pinyin(c["ch"], style=Style.INITIALS, strict=False)[0]
        c["final"] = lazy_pinyin(c["ch"], style=Style.FINALS, strict=False)[0]
    lm = landmarks(x)
    print(cue, "landmarks", " ".join(f"{t + s0:.2f}{k[0]}" for t, k in lm))
    snap_to_landmarks(chars, lm, len(x) / SR)
    # 末字结束 = 末段有声尾（之后进休止闭嘴）
    act = np.flatnonzero(np.convolve(env, np.ones(5) / 5, mode="same") > gate)
    if len(act):
        chars[-1]["end"] = max(chars[-1]["start"] + .1, act[-1] / 100 + .02)
    for c in chars:
        c["start"], c["end"] = round(c["start"] + s0, 3), round(c["end"] + s0, 3)
        c["dtwStart"], c["dtwEnd"] = round(c["dtwStart"] + s0, 3), round(c["dtwEnd"] + s0, 3)
    clips.append({"cue": cue, "character": ARGS.character, "text": text, "start": s0, "duration": dur, "chars": chars,
                  "energyRate": 100, "energy": [round(float(v), 6) for v in env], "gate": round(gate, 6)})
    clips[-1]["breaths"] = [round(t + s0, 3) for t, k in lm if k == "breath"]
    print(cue, " ".join(f"{c['ch']}{c['start']:.2f}[{c['landmark']}]({c['start']-c['dtwStart']:+.2f})" for c in chars))

OUT.write_text(json.dumps({
    "method": "known-text Whisper DTW on final placed Noya stem + monotonic DP snap to acoustic landmarks (fricative burst / voicing onset / pitch step / legato dip, ±0.45s), 30ms anticipation",
    "source": str(STEM).replace("\\", "/"), "sourceSha256": hashlib.sha256(STEM.read_bytes()).hexdigest(),
    "timebase": "stem/mix seconds", "clips": clips}, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", OUT)
