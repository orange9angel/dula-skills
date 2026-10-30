#!/usr/bin/env python3
"""分层音频「算法听审」报告（只读）：配音/唱段、配乐、环境床、拟音、总混音各自的可测指标 + 层间关系。
这是证据与回归门，不是审美结论；正常速度人耳听审不可替代。

用法：
  python audio_report.py --layer vocal=stems/noya.wav --layer music=stems/bed.wav \
      --layer ambience=sfx/roomtone.wav --layer foley=stems/foley.wav --layer mix=mix.wav \
      [--text 已知台词或歌词] [--cues foley_cues.json] [--aesthetics] [--window 30 38] [--out report.json]
层类型：dialogue | vocal | music | ambience | foley | mix（同类型可重复，按 name=path 或 kind:name=path 指定）
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import librosa
import numpy as np

SR = 22050
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTES = "C C# D D# E F F# G G# A A# B".split()


def load(path, win):
    y, _ = librosa.load(path, sr=SR, mono=True, offset=win[0] if win else 0.0, duration=(win[1] - win[0]) if win else None)
    return y


def loudness(path, win):
    cmd = ["ffmpeg", "-hide_banner", "-nostats"] + (["-ss", str(win[0]), "-t", str(win[1] - win[0])] if win else []) + \
          ["-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    tail = err[err.rfind("Summary:"):]
    g = lambda k: (lambda m: float(m.group(1)) if m else None)(re.search(k + r":\s+(-?[\d.]+|-inf)", tail))
    return {"integratedLUFS": g("I"), "loudnessRangeLU": g("LRA"), "truePeakDBFS": g("Peak")}


def env(y, hop):
    return np.sqrt(np.mean(y[:len(y) // hop * hop].reshape(-1, hop) ** 2, axis=1) + 1e-12)


def vocal_metrics(y, text):
    f0, vf, _ = librosa.pyin(y, fmin=70, fmax=1000, sr=SR, frame_length=2048, hop_length=256)
    m = librosa.hz_to_midi(f0[~np.isnan(f0)]) if np.any(~np.isnan(f0)) else np.array([])
    e = env(y, 2205)  # 100ms
    gate = np.percentile(e, 90) * .08
    on = e > gate
    pauses, run = [], 0
    for v in list(on) + [True]:
        if not v:
            run += 1
        else:
            if run >= 3:
                pauses.append(run / 10)
            run = 0
    out = {"voicedShare": round(float(np.mean(vf)), 3),
           "pitchMedianNote": librosa.midi_to_note(float(np.median(m))) if len(m) else None,
           "pitchRangeSemitones(p5-p95)": round(float(np.percentile(m, 95) - np.percentile(m, 5)), 1) if len(m) else None,
           "pauses>=0.3s": len(pauses), "longestPause": max(pauses, default=0)}
    # 颤音：音高曲线 4-8Hz 调制深度（持续音段）
    if len(m) > 64:
        hp = m - np.convolve(m, np.ones(15) / 15, mode="same")
        out["vibratoDepthCents(rms)"] = round(float(np.sqrt(np.mean(hp[7:-7] ** 2)) * 100), 1)
    if text:
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("small", device="cpu", compute_type="int8", local_files_only=True)
            segs, _ = model.transcribe(y.astype(np.float32) if SR == 16000 else librosa.resample(y, orig_sr=SR, target_sr=16000),
                                       language="zh")
            hyp = re.sub(r"[^一-鿿]", "", "".join(s.text for s in segs))
            ref = re.sub(r"[^一-鿿]", "", text)
            out["asr"] = hyp
            out["charErrorRate"] = round(cer(ref, hyp), 3)
        except Exception as ex:  # 模型不在本地时只跳过这一项
            out["asr"] = f"unavailable: {ex}"
    return out


def cer(r, h):
    d = np.arange(len(h) + 1)
    for i, rc in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hc in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rc != hc))
    return d[len(h)] / max(1, len(r))


def music_metrics(y):
    tempo, beats = librosa.beat.beat_track(y=y, sr=SR, hop_length=512)
    bt = librosa.frames_to_time(beats, sr=SR, hop_length=512)
    ib = np.diff(bt)
    chroma = librosa.feature.chroma_cqt(y=y, sr=SR).mean(axis=1)
    best = max(((np.corrcoef(np.roll(p, k), chroma)[0, 1], NOTES[k] + q) for p, q in ((KS_MAJOR, " major"), (KS_MINOR, " minor"))
                for k in range(12)))
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    arc = [round(float(20 * np.log10(np.mean(rms[a:b]) + 1e-9)), 1) for a, b in zip(beats[:-1:4], beats[4::4])]
    on = librosa.onset.onset_detect(y=y, sr=SR, units="time")
    # 段落边界：chroma+MFCC 自相似新颖度
    feat = np.vstack([librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=2048), librosa.feature.mfcc(y=y, sr=SR, hop_length=2048, n_mfcc=13)])
    k = max(2, min(8, int(len(y) / SR / 8)))
    bounds = librosa.segment.agglomerative(feat, k)
    return {"tempoBPM": round(float(np.atleast_1d(tempo)[0]), 1), "beatIntervalCV": round(float(ib.std() / ib.mean()), 3) if len(ib) > 2 else None,
            "keyEstimate": best[1], "keyConfidence": round(float(best[0]), 2), "onsetsPerSecond": round(len(on) / (len(y) / SR), 2),
            "barLoudnessArcDB": arc, "sectionBoundariesSec": [round(float(t), 2) for t in librosa.frames_to_time(bounds, sr=SR, hop_length=2048)]}


def ambience_metrics(y):
    """口径与 build-ambience-foley 底床三门一致：每秒 RMS max/mean<1.4；50ms 包络在 0.5-1s 滞后的自相关<0.15；
    4-8kHz 嘶声占比<0.2。门限针对混音中实际放置的底床，原素材数值仅作参考。"""
    e1 = env(y, SR)
    e = env(y, int(.05 * SR))
    e = e - e.mean()
    ac = np.correlate(e, e, "full")[len(e) - 1:]
    ac = ac / (ac[0] + 1e-12)
    per = float(ac[10:21].max()) if len(ac) > 21 else None
    S = np.abs(librosa.stft(y, n_fft=2048)) ** 2
    fr = librosa.fft_frequencies(sr=SR, n_fft=2048)
    mm = float(e1.max() / e1.mean()) if len(e1) else None
    hiss = float(S[(fr >= 4000) & (fr <= 8000)].sum() / S.sum())
    return {"maxOverMean(1s)": round(mm, 3) if mm else None, "periodicity(0.5-1s)": round(per, 3) if per is not None else None,
            "hissShare(4-8kHz)": round(hiss, 3), "spectralFlatness": round(float(librosa.feature.spectral_flatness(S=np.sqrt(S)).mean()), 4),
            "bedGates": {"maxOverMean<1.4": mm is not None and mm < 1.4, "periodicity<0.15": per is not None and per < .15, "hiss<0.2": hiss < .2}}


def foley_metrics(y, cues, t0):
    on = librosa.onset.onset_detect(y=y, sr=SR, units="time", backtrack=True) + t0
    out = {"onsets": [round(float(t), 3) for t in on]}
    if cues:
        miss = []
        for c in cues:
            d = np.min(np.abs(on - c)) if len(on) else 9
            if d > .15:
                miss.append([c, round(float(d), 3)])
        out["cuesOutside±0.15s"] = miss
        out["cueCount"] = len(cues)
    return out


def relations(layers):
    """层间关系：人声被配乐遮蔽（1-4kHz 语音带、人声有声帧的 SMR）、配乐在人声下的避让量。"""
    rel = {}
    voc = [l for l in layers if l["kind"] in ("dialogue", "vocal")]
    mus = [l for l in layers if l["kind"] == "music"]
    for v in voc:
        for m in mus:
            n = min(len(v["y"]), len(m["y"]))
            Sv = np.abs(librosa.stft(v["y"][:n], n_fft=2048, hop_length=2205)) ** 2
            Sm = np.abs(librosa.stft(m["y"][:n], n_fft=2048, hop_length=2205)) ** 2
            fr = librosa.fft_frequencies(sr=SR, n_fft=2048)
            b = (fr > 1000) & (fr < 4000)
            ev, em = Sv[b].sum(0), Sm[b].sum(0)
            voiced = Sv.sum(0) > np.percentile(Sv.sum(0), 90) * .05
            smr = 10 * np.log10((ev[voiced] + 1e-12) / (em[voiced] + 1e-12))
            mt = 10 * np.log10(Sm.sum(0) + 1e-12)
            rel[f"{v['name']}↔{m['name']}"] = {
                "speechBandSMRmedianDB": round(float(np.median(smr)), 1) if len(smr) else None,
                "maskedFrameShare(SMR<0dB)": round(float(np.mean(smr < 0)), 3) if len(smr) else None,
                "musicDuckUnderVoiceDB": round(float(np.mean(mt[voiced]) - np.mean(mt[~voiced])), 1) if voiced.any() and (~voiced).any() else None}
    return rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", action="append", required=True)
    ap.add_argument("--text")
    ap.add_argument("--cues")
    ap.add_argument("--window", nargs=2, type=float)
    ap.add_argument("--aesthetics", action="store_true", help="Meta Audiobox Aesthetics: CE/CU/PC/PQ (1-10)")
    ap.add_argument("--out")
    a = ap.parse_args()
    win = a.window
    cues = json.loads(Path(a.cues).read_text(encoding="utf-8")) if a.cues else None
    layers = []
    for spec in a.layer:
        name, path = spec.split("=", 1)
        kind = name.split(":")[0] if ":" in name else re.sub(r"\d+$", "", name)
        name = name.split(":")[-1]
        y, lw = load(path, win), win
        if win and len(y) < SR * .5 * (win[1] - win[0]):  # 素材不在时间线坐标上（短于窗口起点）→ 整段分析
            y, lw = load(path, None), None
        layers.append({"name": name, "kind": kind, "path": path, "y": y, "win": lw})
    pred = None
    if a.aesthetics:
        import torch
        from audiobox_aesthetics.infer import initialize_predictor  # 本地 torch 推理；torchaudio 读盘依赖 FFmpeg DLL，故传张量
        pred = initialize_predictor()
    rep = {"window": win, "layers": {}}
    for l in layers:
        y, r = l["y"], {"kind": l["kind"], "path": l["path"], "window": l["win"], **loudness(l["path"], l["win"])}
        if l["kind"] in ("dialogue", "vocal"):
            r.update(vocal_metrics(y, a.text))
        elif l["kind"] == "music":
            r.update(music_metrics(y))
        elif l["kind"] == "ambience":
            r.update(ambience_metrics(y))
        elif l["kind"] == "foley":
            r.update(foley_metrics(y, cues, l["win"][0] if l["win"] else 0))
        elif l["kind"] == "mix":
            r.update({"music": music_metrics(y)})
        if pred is not None:
            r["aesthetics"] = {k: round(float(v), 2) for k, v in pred.forward([{"path": torch.tensor(y[None]).float(), "sample_rate": SR}])[0].items()}
        rep["layers"][l["name"]] = r
    rep["relations"] = relations(layers)
    s = json.dumps(rep, ensure_ascii=False, indent=1)
    print(s)
    if a.out:
        Path(a.out).write_text(s, encoding="utf-8")


if __name__ == "__main__":
    main()
