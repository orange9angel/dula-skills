"""口型能量包络派生：最终放置的人声 PCM → config/voice_envs.json。

工艺口径（build-character-voice 2026-10-14）：从最终放置的 PCM 分轨做 20ms 能量口型，
静默阈值以下归零，非发声窗外为零——**这是能量开合，不是音素视素，也不是戏感验收**。
下游 cel 侧由 draw-over-animation 的 locked-variant-face/raster-face 做三态迟滞选 cel；
viewer 按 (t - t0) / dt 索引 jaw[]。

晋升说明（2026-10-29）：算法原样来自 borrowed_moonlight/tools/build_voice_envs.py
（已认可成片 R5 在用，JAW 口径未改动一个系数），此处仅做三件事：
  1. episode 路径参数化，不再写死 parents[1]；
  2. 行来源从单一 config/dialogue.json 推广为显式 lines 配置；
  3. 新增 span 取窗，支持唱段——唱段人声埋在音乐混音里，须先分离人声总线
     （Demucs），再按唱句边界取窗；禁止用未分离的原歌包络（song-lipsync 验收纪律）。
原先同类实现散落在 stardust_clad_s1e1/tools/build_audio.py、borrowed_moonlight 与
bio_armor_academy_s1e1，按 AGENTS.md「不能只写回经验却把可执行收益留在单集 tools/」收敛到此。
DTW 逐字链不在本文件范围，正本在 dula-assets/lib/audio/。

用法：
  python build_voice_envs.py EPISODE_DIR --config config/voice_env_lines.json
  python build_voice_envs.py EPISODE_DIR            # 回退读 config/dialogue.json

lines 配置（任一形式）：
  {"lines":[{"id":"m03","speaker":"...","character":"noya","t0":198.0,
             "pcm":"assets/audio/dialogue/m03.wav"},
            {"id":"song_l1","character":"noya","t0":201.0,
             "pcm":"tmp/demucs/htdemucs/x/vocals.wav","span":[3.0,6.0],
             "window":3.0,"lyric":"你不必把沉默解释清楚"}]}
span 为该 pcm 内的 [start,end] 秒；省略则取整条。
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

import numpy as np

SR = 48000
DT = .02


def load(path, span=None):
    cmd = ['ffmpeg', '-v', 'error']
    if span:
        cmd += ['-ss', str(span[0]), '-t', str(round(span[1] - span[0], 6))]
    cmd += ['-i', str(path), '-ar', str(SR), '-ac', '1', '-f', 'f32le', '-']
    raw = subprocess.check_output(cmd)
    return np.frombuffer(raw, np.float32).astype(np.float64)


def jaw_track(x):
    """20ms RMS → 30ms hanning 平滑 → 归一到峰值*.85 → 低于峰值 8% 归零。

    系数与已认可成片一致，改动需另立版本并重新验收。
    """
    hop = round(DT * SR)
    m = len(x) // hop
    if m == 0:
        return []
    env = np.sqrt(np.mean(x[:m * hop].reshape(m, hop) ** 2, axis=1))
    k = np.hanning(5)
    k /= k.sum()
    env = np.convolve(env, k, mode='same')
    peak = max(float(env.max()), 1e-9)
    jaw = np.clip(env / peak * .85, 0, .85)
    jaw[env < peak * .08] = 0.0
    return [round(float(v), 4) for v in jaw]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_lines(ep, cfg_path):
    """显式 lines 配置优先；否则回退 borrowed_moonlight 式 config/dialogue.json。"""
    if cfg_path:
        cfg = json.loads((ep / cfg_path).read_text(encoding='utf-8'))
        return cfg['lines'], str(cfg_path)
    dlg_path = ep / 'config/dialogue.json'
    dlg = json.loads(dlg_path.read_text(encoding='utf-8'))
    out = []
    for line in dlg['lines']:
        out.append({**line, 't0': line['t'],
                    'pcm': f"assets3d/dialogue/{line['id']}.wav"})
    return out, 'config/dialogue.json'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('episode')
    ap.add_argument('--config', default=None,
                    help='lines 配置路径（相对 episode）；省略则读 config/dialogue.json')
    ap.add_argument('--output', default='config/voice_envs.json')
    a = ap.parse_args()
    ep = Path(a.episode).resolve()
    if not ep.is_dir():
        sys.exit(f'episode not found: {ep}')

    raw_lines, origin = resolve_lines(ep, a.config)
    lines, srcs, over = [], {}, []
    for ln in raw_lines:
        pcm = ep / ln['pcm']
        if not pcm.exists():
            sys.exit(f"missing pcm for {ln['id']}: {pcm}")
        span = ln.get('span')
        x = load(pcm, span)
        jaw = jaw_track(x)
        dur = round(len(x) / SR, 3)
        rec = {'id': ln['id'], 't0': ln['t0'], 'dur': dur, 'dt': DT, 'jaw': jaw,
               'source_pcm': ln['pcm']}
        for opt in ('speaker', 'character', 'lyric', 'role_status'):
            if opt in ln:
                rec[opt] = ln[opt]
        if span:
            rec['source_span'] = span
        lines.append(rec)
        srcs[ln['id']] = sha(pcm)
        voiced = sum(1 for v in jaw if v > 0)
        win = ln.get('window')
        flag = ''
        if win is not None and dur > win + .2:
            over.append(ln['id'])
            flag = f'  !! 超窗 {dur - win:+.2f}s'
        print(f"{ln['id']:>14} t0={ln['t0']:8.2f} dur={dur:6.2f}s "
              f"jaw={len(jaw):4d} frames  发声{voiced / max(len(jaw), 1) * 100:5.1f}%"
              f"{flag}", flush=True)

    out = {
        'source': f'derived from {origin}; pcm placed at lines[].t0 (mix zero point)',
        'method': '20ms RMS energy envelope, 30ms hanning smooth, '
                  'silence gate 8% of line peak',
        'discipline': '能量开合，不是音素视素，也不是戏感验收；'
                      '摆点或时长变更后必须重派生并随之重渲',
        'dt': DT,
        'generator': 'dula-skills/build-character-voice/scripts/build_voice_envs.py',
        'source_files': srcs,
        'lines': lines,
    }
    (ep / a.output).write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(f"\nvoice_envs: {len(lines)} lines -> {a.output}; 超窗: {over or '无'}")


if __name__ == '__main__':
    main()
