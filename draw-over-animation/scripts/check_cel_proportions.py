#!/usr/bin/env python3
"""跨画人体一致性入库门（人工地标表比对版）。

教训来源（2026-10-25《半拍晴天》）：自动检测解剖地标在动漫 cel 上不可靠
（alpha 几何被头发/裙摆/姿势污染；色带规则被同名色污染——白衬衫规则吃到
皮肤高光与亮纹，两版自动实现都产出假绿/假红，已废弃）。

可靠做法：agent 在刻度图（grid overlay）上**人工读**每张画的地标行
（腰线/裙摆/袜口/裆/肩线等，按角色服装选），写成表；本工具只做
"与锚表比对、超差驳回"的机械执行——测量判断归人，执行归机器。

驳回先复查锚（borrowed_moonlight A2）：多张画在同一 band 上同向系统性偏移
（如全员 boot_top +0.03）几乎总是**锚表读数错**而非画错——把锚图该区域放大
复读（ReadMediaFile region 原分辨率裁片）再决定是否返工；零散单画超差才是画错。
刻度图上粗读易把"衣襟线/最下方挂饰"误当"马甲下沿"，差出 5% 身高。

landmarks json（每张画一份）：
{"H": 1505,
 "bands": {"waist": {"top": 0.350, "bottom": 0.360},   # 相对全身高占比
           "hem":   {"top": 0.430, "bottom": 0.544},
           "sock":  {"top": 0.601, "bottom": 0.95}}}
bands 的键集合各画必须一致；top/bottom 至少给一个。

用法：
  python check_cel_proportions.py --anchor anchor.json --cels a.json b.json \
      [--tolerance 0.03] [--report out.json]
exit 0=全过，2=有驳回，1=用法错误。
"""
import argparse, json, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--anchor', required=True)
    ap.add_argument('--cels', nargs='+', required=True)
    ap.add_argument('--tolerance', type=float, default=0.03)
    ap.add_argument('--report')
    a = ap.parse_args()
    ref = json.load(open(a.anchor, encoding='utf-8'))
    out = {'anchor': a.anchor, 'tolerance': a.tolerance, 'cels': []}
    bad = 0
    for p in a.cels:
        m = json.load(open(p, encoding='utf-8'))
        diffs, fails = {}, []
        for bn, rb in ref['bands'].items():
            cb = m['bands'].get(bn)
            if cb is None:
                diffs[bn] = 'missing'; fails.append(bn); continue
            d = {}
            for k in ('top', 'bottom'):
                if k in rb and k in cb:
                    d[k] = round(cb[k] - rb[k], 4)
                    if abs(d[k]) > a.tolerance:
                        fails.append(f'{bn}.{k}')
            diffs[bn] = d
        out['cels'].append({'path': p, 'diff_vs_anchor': diffs,
                            'rejected': bool(fails), 'fail_fields': fails})
        bad += bool(fails)
    if a.report:
        json.dump(out, open(a.report, 'w'), ensure_ascii=False, indent=2)
    for c in out['cels']:
        mark = 'REJECT' if c['rejected'] else 'ok'
        ds = ' '.join(f"{k}{v}" for k, v in c['diff_vs_anchor'].items())
        print(f"{mark:6s} {c['path'].split('/')[-1]:36s} {ds}")
    return 2 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
