"""episode_gate.py — viewer 链 episode 一条命令总验收（物理世界完整性门禁）。

对一个 episode 目录依次执行：
  ① render.mjs --check（带探针串，产 trace + 检查帧 + seek 校验；--skip-render 复用现有 trace）
  ② contact_probe（经 tools/check_contact.py 薄包装 + config/contact_contract.json）
  ③ check_locomotion.py（trace 里存在 locomotion 段时）
  ④ check_audio_sync.py（存在 assets3d/mixed.wav 且该检查件存在时）
  ⑤ 逐拍近景审片组（存在 config/review_shots.json 时，render.mjs --shots 出帧）
  ⑥ flicker 渲染稳定性（存在成片 + config/flicker_watch.json 时：
     flicker_probe.py 逐帧二阶差分，watch 区+背景粗扫；用最近一次 render 后的成片）

汇总 gate_report.json（默认 <episode>/storyboard/gate/）+ 人类可读摘要；
contact 失败按 config/timeline.json 定位到节拍（段 id）。

用法（在 dula-story 根或任意目录，用仓库 venv）：
  .venv/Scripts/python.exe ../dula-skills/direct-animation-craft/scripts/episode_gate.py \
      ./episodes/<episode> [--skip-render] [--board storyboard/gate] [--probe-q "&probe-door=1&probe-bento=1"]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def run_step(name, cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return {'name': name, 'cmd': ' '.join(str(c) for c in cmd), 'returncode': p.returncode,
            'passed': p.returncode == 0, 'tail': (p.stdout + p.stderr).strip().splitlines()[-5:]}


def beat_of(timeline, t):
    for s in timeline.get('segments', []):
        if s['start'] <= t < s['end']:
            return s['id']
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('episode', type=Path)
    ap.add_argument('--skip-render', action='store_true', help='复用已有 trace，不重渲 check')
    ap.add_argument('--board', default='storyboard/gate', help='报告与帧输出目录（episode 相对）')
    ap.add_argument('--probe-q', default='&probe-door=1&probe-bento=1', help='探针查询串')
    args = ap.parse_args()
    ep = args.episode.resolve()
    board = ep / args.board
    board.mkdir(parents=True, exist_ok=True)
    trace = board / 'trace.json'
    rel_board, rel_trace = args.board, f'{args.board}/trace.json'  # render.mjs 只接 episode 相对路径
    steps = []

    # ① check 渲染（探针 trace + 抽帧 + seek）
    if args.skip_render:
        ok = trace.exists()
        steps.append({'name': 'render_check', 'passed': ok, 'skipped': True,
                      'note': f'reuse {trace}' if ok else f'trace missing: {trace}'})
        if not ok:
            print(f'gate FAIL: --skip-render 但 {trace} 不存在')
            sys.exit(2)
    else:
        steps.append(run_step('render_check', [
            'node', 'render.mjs', '--check', '--board', rel_board, '--trace', rel_trace,
            '--q', args.probe_q], ep))

    # seek 一致性（check 模式产物）
    seek_file = board / 'seek_check.json'
    if steps[-1]['passed'] and seek_file.exists():
        seek = json.loads(seek_file.read_text(encoding='utf-8'))
        steps.append({'name': 'seek_determinism', 'passed': seek.get('passed', False),
                      'note': f"{len(seek.get('checks', []))} checks"})

    # ② 接触/物理探针
    wrapper = ep / 'tools/check_contact.py'
    if wrapper.exists() and trace.exists():
        steps.append(run_step('contact_probe', [sys.executable, str(wrapper), str(trace)], ep))
    else:
        steps.append({'name': 'contact_probe', 'passed': False, 'note': 'tools/check_contact.py 缺失'})

    # ③ 步态检查（trace 有 locomotion 段才跑）
    loco = ep / 'tools/check_locomotion.py'
    has_loco = False
    if trace.exists():
        has_loco = '"locomotion"' in trace.read_text(encoding='utf-8')
    if loco.exists() and has_loco:
        steps.append(run_step('locomotion', [sys.executable, str(loco), str(trace)], ep))

    # ④ 声画对位（有混音与检查件才跑）
    audio_check = ep / 'tools/check_audio_sync.py'
    if audio_check.exists() and (ep / 'assets3d/mixed.wav').exists():
        steps.append(run_step('audio_sync', [sys.executable, str(audio_check)], ep))

    # ⑤ 逐拍近景审片组（有镜表才出）
    shots = ep / 'config/review_shots.json'
    if shots.exists():
        steps.append(run_step('review_shots', [
            'node', 'render.mjs', '--check', '--shots', 'config/review_shots.json',
            '--board', f'{args.board}/shots'], ep))

    # ⑥ 渲染稳定性（成片存在 + watch 配置存在才跑；成片必须比源码新，否则判陈旧跳过）
    flicker_watch = ep / 'config/flicker_watch.json'
    video = ep / 'output/craft3d_full.mp4'
    probe = Path(__file__).with_name('flicker_probe.py')
    if flicker_watch.exists() and video.exists():
        # 成片陈旧（比画面源码旧）时跳过：陈旧片的闪烁结果无意义
        srcs = [ep / p for p in ('viewer.js', 'performance.js', 'scenes/RooftopNoonScene.js')]
        srcs = [p for p in srcs if p.exists()]
        stale = srcs and video.stat().st_mtime < max(p.stat().st_mtime for p in srcs)
        if stale:
            steps.append({'name': 'flicker', 'passed': True, 'skipped': True,
                          'note': 'video older than sources; render --out 后再跑'})
        else:
            steps.append(run_step('flicker', [sys.executable, str(probe), str(video),
                '--watch', str(flicker_watch), '--out', str(board / 'flicker_report.json')], ep))

    # contact 失败定位到节拍
    beat_map = {}
    timeline_file = ep / 'config/timeline.json'
    validation = trace.with_name('contact_validation.json')
    if timeline_file.exists() and validation.exists():
        timeline = json.loads(timeline_file.read_text(encoding='utf-8'))
        report = json.loads(validation.read_text(encoding='utf-8'))
        for f in report.get('failures', []):
            m = re.search(r'@t=([\d.]+)', f)
            if m:
                beat = beat_of(timeline, float(m.group(1)))
                beat_map.setdefault(beat or f"t={m.group(1)}", 0)
                beat_map[beat or f"t={m.group(1)}"] += 1

    passed = all(s.get('passed') for s in steps)
    report = {'episode': ep.name, 'passed': passed,
              'steps': steps, 'contact_failures_by_beat': beat_map,
              'note': '物理完整性=断言绿+审片全+声画绿；审片帧（shots/）仍需人工过五点清单'}
    (board / 'gate_report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'\n=== episode gate: {ep.name} ===')
    for s in steps:
        mark = 'PASS' if s.get('passed') else 'FAIL'
        extra = f" — {s.get('note', '')}" if s.get('note') else ''
        print(f'  [{mark}] {s["name"]}{extra}')
    if beat_map:
        print('  contact 失败按节拍定位：')
        for beat, n in sorted(beat_map.items(), key=lambda x: -x[1]):
            print(f'    {beat}: {n} 条')
    print(f'gate {"ALL GREEN" if passed else "FAIL"} → {board / "gate_report.json"}')
    sys.exit(0 if passed else 2)


if __name__ == '__main__':
    main()
