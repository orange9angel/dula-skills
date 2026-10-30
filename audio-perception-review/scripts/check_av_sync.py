#!/usr/bin/env python3
"""声画同步与动作流畅度探测（只读）。真值来自音频与成片像素，不信 viewer 的参数：
  口型  —— 诺娅最终分轨 10ms 能量（逐段门限 + 67ms 余音）判有声；逐字韵母推期望口型类；
          对照探针 states 里**实际显示**的嘴（mouth=='drawn' 表示原画画死的嘴，不受控）。
          指标：休止张嘴帧、有声闭嘴帧、口型类匹配率、逐字起音时差（显示到对的嘴的首帧 − 字起点）。
  表情  —— 句前吸气是否出现；唱长音中途眨眼计数（近景）。
  动作  —— 换画时刻：每镜头停帧分布、落在八分音符网格 ±1 帧的比例；
          成片 mp4 逐帧差分：换画跳变 / 中位运动 = 跳帧比（>3 记为一次「跳」），以及无运动静止帧占比。
用法：python check_av_sync.py STATES.json MP4 --align ALIGN.json --beats BEATS.npy --mix MIX.wav --t0 30 [--who noya]
STATES 由 probe_viewer_states.mjs 采集：每帧 {t, shot, drawings|face, <who>:{faceVisible, mouth, eyes}}；
mouth ∈ rest/labial/inhale/narrow/open/round，或 'drawn'（原画画死的嘴，不受控）。
BEATS：整首歌的节拍网格（秒，与 STATES 同零点）；短窗口里重测速度不可靠（8s 窗口实测 108/215 BPM vs 全曲 146.5）。
"""
import argparse
import json
import subprocess
from pathlib import Path

import librosa
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("states")
ap.add_argument("mp4")
ap.add_argument("--align", required=True)
ap.add_argument("--beats", required=True)
ap.add_argument("--mix", required=True)
ap.add_argument("--who", default="noya")
ap.add_argument("--t0", type=float, default=30.0)
ap.add_argument("--report")
a = ap.parse_args()

S = json.loads(Path(a.states).read_text(encoding="utf-8"))
fps, states = S["fps"], S["states"]
AL = json.loads(Path(a.align).read_text(encoding="utf-8"))
beats = np.load(a.beats)
grid = np.sort(np.concatenate([beats, (beats[:-1] + beats[1:]) / 2]))  # 八分音符


def truth(t):
    """有声真值：段内能量门 + 67ms 余音；换气（clips[].breaths 到下一字起点）不算唱；末字结束后 100ms 内的释放尾不判闭嘴错。"""
    for c in AL["clips"]:
        for b in c.get("breaths", []):
            nxt = min([x["start"] for x in c["chars"] if x["start"] > b], default=b + .3)
            if b <= t < nxt:
                return False, None
        if c["chars"] and c["chars"][-1]["end"] <= t < c["chars"][-1]["end"] + .1:
            return False, None
        if c["start"] - .04 <= t < c["start"] + c["duration"] + .15:
            e = np.array(c["energy"])
            k0, k1 = int((t - .067 - c["start"]) * 100), int((t - c["start"]) * 100)
            win = e[max(0, k0):max(0, k1) + 1]
            voiced = len(win) > 0 and win.max() > c["gate"]
            ch = next((x for x in c["chars"] if x["start"] <= t + .025 < x["end"]), None)
            return voiced, ch
    return False, None


def expect(ch, t):
    f = ch["final"]
    phase = (t + .025 - ch["start"]) / max(.04, ch["end"] - ch["start"])
    if ch["initial"] in ("b", "p", "m") and t < ch["start"] + .035:
        return {"labial"}
    if any(v in f for v in "uüvo") and not any(v in f for v in "aei"):
        return {"round"}
    if any(v in f for v in "ao") and not (f[:1] in "iu" and phase < .2) and not (f.endswith("i") and phase > .72):
        return {"open"}
    return {"narrow"}


OPEN = {"open", "narrow", "round", "drawn"}
for s in states:  # 统一取被检角色
    s["noya"] = s.get(a.who) or {"faceVisible": False}
rep = {"lip": {}, "expression": {}, "motion": {}}
vis = [s for s in states if (s.get("noya") or {}).get("faceVisible")]
sil_open = [s["t"] for s in vis if not truth(s["t"])[0] and s["noya"]["mouth"] in OPEN]
voi_closed = [s["t"] for s in vis if truth(s["t"])[0] and s["noya"]["mouth"] not in OPEN | {"labial"}]
drawn = [s["t"] for s in vis if s["noya"]["mouth"] == "drawn"]
match, total = 0, 0
for s in vis:
    v, ch = truth(s["t"])
    if v and ch:
        total += 1
        match += s["noya"]["mouth"] in expect(ch, s["t"])
lags = []
for c in AL["clips"]:
    for k, ch in enumerate(c["chars"]):
        prev = c["chars"][k - 1] if k else None
        if prev and expect(prev, prev["end"] - .03) & expect(ch, ch["start"]):
            lags.append((ch["ch"], round(ch["start"], 2), "continuous"))  # 与前字同口型：无换形可测
            continue
        fr = [s for s in vis if ch["start"] - .1 <= s["t"] < ch["end"]]
        if not fr:
            continue
        hit = next((s for s in fr if s["noya"]["mouth"] in expect(ch, s["t"])), None)
        lags.append((ch["ch"], round(ch["start"], 2), None if hit is None else round(hit["t"] - ch["start"], 3)))
bad_lag = [x for x in lags if x[2] != "continuous" and (x[2] is None or not -.075 <= x[2] <= .1)]
# 开合跟声：显示嘴的开度（rest/labial 0、inhale .15、narrow/round .5、open 1）与该帧人声能量（段内 p80 归一）的相关。
# 借月光的少女口径：观众读「同步」主要读开合随声音强弱起落，而不是韵母形状。
OPENNESS = {"rest": 0, "labial": 0, "inhale": .15, "narrow": .5, "round": .5, "open": 1}
def energy_at(t):
    for c in AL["clips"]:
        if c["start"] <= t < c["start"] + c["duration"]:
            e = np.array(c["energy"])
            k = int((t - c["start"]) * 100)
            return float(e[k:k + 3].mean()) / (np.percentile(e[e > c["gate"]], 80) + 1e-9) if len(e[e > c["gate"]]) else 0.0
    return 0.0
ctrl = [s for s in vis if s["noya"]["mouth"] in OPENNESS]
oc = float(np.corrcoef([OPENNESS[s["noya"]["mouth"]] for s in ctrl], [energy_at(s["t"]) for s in ctrl])[0, 1]) if len(ctrl) > 5 else None
sw = sum(1 for i in range(1, len(ctrl)) if ctrl[i]["noya"]["mouth"] != ctrl[i - 1]["noya"]["mouth"])
rep["lip"] = {"opennessVsVoiceEnergyCorr": None if oc is None else round(oc, 3), "mouthChangesPerSecond": round(sw / max(1e-9, len(ctrl) / fps), 2),
              "visibleFaceFrames": len(vis), "silenceOpenFrames": len(sil_open), "voicedClosedFrames": len(voi_closed),
              "uncontrolledDrawnMouthFrames": len(drawn), "visemeMatch": round(match / max(1, total), 3),
              "charOnsetLags": lags, "badOnsets": bad_lag,
              "silenceOpenAt": [round(t, 2) for t in sil_open[:12]], "voicedClosedAt": [round(t, 2) for t in voi_closed[:12]]}

# 表情：句前吸气、近景长音中途眨眼
inh = []
for c in AL["clips"]:
    t0 = c["chars"][0]["start"]
    fr = [s for s in vis if t0 - .4 <= s["t"] < t0]
    if fr:
        inh.append((c["text"][:3], any(s["noya"]["mouth"] == "inhale" for s in fr)))
blink_mid = [s["t"] for s in vis if s["noya"].get("eyes") == "closed" and truth(s["t"])[0]]
rep["expression"] = {"preInhale": inh, "blinkWhileSinging": [round(t, 2) for t in blink_mid]}

# 动作：换画时刻
shots = {}
for s in states:
    shots.setdefault(s["shot"], []).append(s)
mot = {}
for sid, fr in shots.items():
    keys = [tuple(s.get("drawings") or [s.get("face")]) for s in fr]
    ch = [fr[i]["t"] for i in range(1, len(fr)) if keys[i] != keys[i - 1]]
    holds, last = [], fr[0]["t"]
    for t in ch + [fr[-1]["t"] + 1 / fps]:
        holds.append(round((t - last) * fps))
        last = t
    on = [t for t in ch if np.min(np.abs(grid - t)) <= 1.01 / fps]
    mot[sid] = {"changes": len(ch), "holdFrames": holds, "meanHold": round(float(np.mean(holds)), 1),
                "onEighthGrid": f"{len(on)}/{len(ch)}"}
# 像素：成片逐帧差分（去掉下缘观众带）
raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", a.mp4, "-vf", "scale=320:180,format=gray", "-f", "rawvideo", "-"])
V = np.frombuffer(raw, np.uint8).reshape(-1, 180, 320)[:, :150].astype(np.float32)
d = np.abs(np.diff(V, axis=0)).mean(axis=(1, 2))
cuts = {round((s["t"] - a.t0) * fps) for i, s in enumerate(states[1:], 1) if s["shot"] != states[i - 1]["shot"]}
for sid, fr in shots.items():
    idx = [round((s["t"] - a.t0) * fps) for s in fr][1:]
    idx = [i for i in idx if i not in cuts and 0 < i < len(d) + 1]
    dd = d[[i - 1 for i in idx]]
    if not len(dd):
        continue
    med = float(np.median(dd)) + 1e-3
    pops = int((dd > 3 * med).sum())
    still = float((dd < .05).mean())
    chg = [round((t - a.t0) * fps) for t in [fr[i]["t"] for i in range(1, len(fr)) if tuple(fr[i].get("drawings") or [fr[i].get("face")]) != tuple(fr[i - 1].get("drawings") or [fr[i - 1].get("face")])]]
    cj = [float(d[i - 1]) for i in chg if 0 < i <= len(d) and i not in cuts]
    mot[sid].update({"meanChangeJump": round(float(np.mean(cj)), 2) if cj else None, "medianMotion": round(med, 3), "maxJumpRatio": round(float(dd.max() / med), 1), "pops": pops,
                     "stillFrameShare": round(still, 2)})
rep["motion"] = mot

# 协调：①Beat Align Score（舞蹈生成常用指标，AIST++）：动作重音时刻对最近音乐拍（四分+八分）的高斯得分；
# 动作重音 = 换画时刻 ∪ 成片运动能量局部峰。②画面运动能量 vs 混音起音强度的互相关（±0.3s 内的最佳时滞）。
mix, sr = librosa.load(a.mix, sr=22050, mono=True)
ons = librosa.onset.onset_strength(y=mix, sr=sr, hop_length=735)  # 30 fps
n = min(len(ons) - 1, len(d))
mv = d[:n].copy()
for c in cuts:
    if 0 < c <= n:
        mv[c - 1] = np.nan  # 剪辑跳变不算动作
mv = np.nan_to_num(mv, nan=float(np.nanmedian(mv)))
o = ons[1:n + 1]
z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
xc = {lag: float(np.mean(z(mv[max(0, lag):n + min(0, lag)]) * z(o[max(0, -lag):n - max(0, lag)]))) for lag in range(-9, 10)}
best = max(xc, key=xc.get)
peaks = [i for i in range(1, n - 1) if mv[i] > mv[i - 1] and mv[i] >= mv[i + 1] and mv[i] > 1.5 * np.median(mv)]
events = sorted({round(a.t0 + (i + 1) / fps, 3) for i in peaks} | {round(t, 3) for sid in shots for t in
                [shots[sid][i]["t"] for i in range(1, len(shots[sid])) if tuple(shots[sid][i].get("drawings") or [shots[sid][i].get("face")]) != tuple(shots[sid][i - 1].get("drawings") or [shots[sid][i - 1].get("face")])]})
sigma = .05
bas = float(np.mean([np.exp(-np.min((grid - e) ** 2) / (2 * sigma ** 2)) for e in events])) if events else 0.0
rep["coordination"] = {"beatAlignScore": round(bas, 3), "accentEvents": len(events),
                       "motionVsMusicOnsetCorr": round(xc[best], 3), "bestLagFrames(+=motion later)": best,
                       "corrAtZeroLag": round(xc[0], 3)}

print(json.dumps(rep, ensure_ascii=False, indent=1))
if a.report:
    Path(a.report).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
