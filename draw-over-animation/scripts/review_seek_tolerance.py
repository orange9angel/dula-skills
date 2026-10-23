"""Review failed exact seek hashes against saved lossless reproduction pairs.

Keeps the original report. A bounded pixel tolerance is explicit and does not
turn failed byte comparisons into exact matches. Pair capture is caller-owned.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    root = Path(args.episode).resolve()
    cfg = json.loads((root / args.config).read_text(encoding='utf-8'))
    if (root / cfg['exact_report']).resolve() == (root / cfg['output']).resolve():
        raise ValueError('Keep the exact report; use a different review output')
    original = json.loads((root / cfg['exact_report']).read_text(encoding='utf-8'))
    pairs = {float(p['t']): p for p in cfg['pairs']}
    report = {**original, 'exact_report': cfg['exact_report'], 'tolerance': cfg['tolerance'], 'reviews': []}
    for check in report['checks']:
        if check['equal']:
            continue
        pair = pairs.get(float(check['t']))
        if not pair:
            continue
        a, b = [np.asarray(Image.open(root / pair[k]).convert('RGBA')).astype(np.int16)
                for k in ['sequential', 'seek']]
        if a.shape != b.shape:
            raise ValueError('Different capture dimensions')
        delta = np.abs(a - b)
        maximum, count = int(delta.max()), int((delta.max(axis=2) > 0).sum())
        allowed = maximum <= cfg['tolerance']['max_channel_delta'] and count <= cfg['tolerance']['max_changed_pixels']
        check['within_pixel_tolerance'] = allowed
        report['reviews'].append({**pair, 'max_channel_delta': maximum, 'changed_pixels': count,
            'passed': allowed, 'sha256': {k: hashlib.sha256((root / pair[k]).read_bytes()).hexdigest()
                                       for k in ['sequential', 'seek']}})
    report['passed'] = all(c['equal'] or c.get('within_pixel_tolerance', False) for c in report['checks'])
    report['note'] = 'Exact mismatches remain false. Tolerance uses independently recaptured PNG pairs, not original full-render checkpoint buffers.'
    (root / cfg['output']).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'reviews': report['reviews']}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
