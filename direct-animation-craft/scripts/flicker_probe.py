"""flicker_probe.py — 渲染稳定性探针（C8）：成片逐帧二阶差分抓高频闪烁。

z-fighting 共面件 / alphaTest 细件被 mipmap 吃掉的特征是像素值 A-B-A 高频振荡；
平滑运动的二阶差分趋零。流式逐帧（内存只留 3 帧），对 watch 区（声明的像素矩形+
时间窗）与全屏 4×4 背景粗扫分别累计 二阶差分均值/峰值/超阈占比，超标即红。

用法：
  python flicker_probe.py <video.mp4> --watch <episode>/config/flicker_watch.json \
      [--out <report.json>] [--work 640x360]
watch 配置：{"regions":[{"name","rect":[x,y,w,h]（1280×720 像素坐标）,"window":[t0,t1],
  "mean_max":均值阈,"frac_max":超阈像素占比阈,"pix":像素二阶差阈值}],
  "bg_grid": {"pix":阈值,"frac_max":占比阈}}
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video', type=Path)
    ap.add_argument('--watch', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=None)
    ap.add_argument('--work', default='640x360')
    ap.add_argument('--t0', type=float, default=0.0, help='剪辑起点偏移（--range 出的片段其 0 点对应的原片秒）')
    ap.add_argument('--bg-fps', type=float, default=30.0, help='成片帧率（窗换算用）')
    args = ap.parse_args()
    W = json.loads(args.watch.read_text(encoding='utf-8'))
    regions = W['regions']
    bg = W.get('bg_grid', {'pix': 30, 'frac_max': .02})
    ww, hh = [int(x) for x in args.work.split('x')]
    fps = args.bg_fps

    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(args.video),
                        '-vf', f'scale={ww}:{hh}', '-pix_fmt', 'gray', f'{td}/f%05d.png'],
                       check=True)
        files = sorted(Path(td).glob('f*.png'))
        n = len(files)
        if n < 3:
            print('too few frames')
            sys.exit(2)

        def region_slice(rect):
            x, y, w, h = rect
            sx, sy = ww / 1280, hh / 720
            return slice(int(y * sy), int((y + h) * sy)), slice(int(x * sx), int((x + w) * sx))

        acc = [{'sum': 0., 'max': 0., 'over': 0, 'cnt': 0, 'sl': region_slice(R['rect']),
                'win': [R.get('window', [0, n / fps])[0] - args.t0, R.get('window', [0, n / fps])[1] - args.t0]}
               for R in regions]
        gy, gx = hh // 4, ww // 4
        bg_cells = bg.get('cells') or [[a, b] for a in range(4) for b in range(4)]
        bgacc = {tuple(c): {'sum': 0., 'over': 0, 'cnt': 0} for c in bg_cells}

        f0 = np.asarray(Image.open(files[0]), dtype=np.float32)
        f1 = np.asarray(Image.open(files[1]), dtype=np.float32)
        for i in range(2, n):
            f2 = np.asarray(Image.open(files[i]), dtype=np.float32)
            d2 = np.abs(f2 * 2 - f1 - f0)  # A-B-A 振荡放大，平滑运动≈0
            t = i / fps
            for A in acc:
                if A['win'][0] <= t <= A['win'][1]:
                    seg = d2[A['sl']]
                    A['sum'] += float(seg.sum())
                    A['max'] = max(A['max'], float(seg.max()))
                    A['over'] += int((seg > 30).sum())
                    A['cnt'] += seg.size
            for a, b in bgacc:
                seg = d2[a * gy:(a + 1) * gy, b * gx:(b + 1) * gx]
                bgacc[(a, b)]['sum'] += float(seg.sum())
                bgacc[(a, b)]['over'] += int((seg > bg['pix']).sum())
                bgacc[(a, b)]['cnt'] += seg.size
            f0, f1 = f1, f2

    report = {'video': str(args.video), 'frames': n, 'regions': [], 'bg': [], 'failures': []}
    for R, A in zip(regions, acc):
        if not A['cnt']:
            continue
        mean = A['sum'] / A['cnt']
        frac = A['over'] / A['cnt']
        row = {'name': R['name'], 'window': A['win'], 'mean': round(mean, 2),
               'max': round(A['max'], 1), 'frac_over': round(frac, 5)}
        report['regions'].append(row)
        if mean > R.get('mean_max', 8) or frac > R.get('frac_max', .01):
            report['failures'].append(
                f"flicker @{R['name']}: mean {mean:.1f} / frac {frac:.4f} over limit")
        if mean < R.get('mean_min', 0):  # 内容消失（alphaTest 被 mip 吃掉）均值趋零——带下限
            report['failures'].append(
                f"flicker @{R['name']}: mean {mean:.1f} below floor {R['mean_min']}（内容消失）")
    for (a, b), A in bgacc.items():
        frac = A['over'] / A['cnt']
        report['bg'].append({'cell': [a, b], 'mean': round(A['sum'] / A['cnt'], 2),
                             'frac_over': round(frac, 5)})
        if frac > bg.get('frac_max', .02):
            report['failures'].append(f"flicker @bg cell ({a},{b}): frac {frac:.4f}")
    report['passed'] = not report['failures']
    out = args.out or args.video.with_suffix('.flicker.json')
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for row in report['regions']:
        print(f"  {row['name']}: mean {row['mean']} max {row['max']} frac {row['frac_over']}")
    if report['failures']:
        print('FAIL', len(report['failures']), 'flicker violations')
        for f in report['failures'][:10]:
            print(' ', f)
        sys.exit(2)
    print('flicker: all regions stable')


if __name__ == '__main__':
    main()
