"""Register an approved donor region without replacing the accepted upper body.

Coordinates and masks are reviewed episode data, never inferred anatomy.
Unlike compose_cel_regions, this may change the target silhouette in its mask.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--episode', type=Path, required=True)
    ap.add_argument('--config', required=True)
    args = ap.parse_args()
    cfg = json.loads((args.episode / args.config).read_text(encoding='utf-8'))
    base = Image.open(args.episode / cfg['base']).convert('RGBA')
    if 'baseCrop' in cfg:
        base = base.crop(cfg['baseCrop'])
    base = np.array(base.resize(cfg['size'], Image.Resampling.LANCZOS))
    donor = np.array(Image.open(args.episode / cfg['donor']).convert('RGBA').crop(cfg['donorCrop']))
    donor[donor[:, :, 3] < cfg.get('alphaCutoff', 0), 3] = 0
    mask = np.zeros(donor.shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.array(cfg['donorPolygon'], np.int32)], 255)
    donor[:, :, 3] = np.minimum(donor[:, :, 3], mask)
    width, height = cfg['size']
    registered = cv2.warpAffine(donor, np.array(cfg['affine'], np.float32), (width, height))
    target = np.zeros((height, width), np.uint8)
    cv2.fillPoly(target, [np.array(cfg['targetPolygon'], np.int32)], 255)
    y0, y1 = cfg['transitionY']
    weight = np.clip((np.arange(height)[:, None] - y0) / (y1-y0), 0, 1) * (target/255)
    output = np.uint8(np.clip(base*(1-weight[:, :, None])+registered*weight[:, :, None], 0, 255))
    if not np.array_equal(output[weight == 0], base[weight == 0]):
        raise ValueError('Protected pixels changed')
    output[(weight > 0) & (output[:, :, 3] == 0)] = 0
    path = args.episode / cfg['output']
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output).save(path)
    report = {'output': cfg['output'], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'protectedPixelDifference': 0, 'note': 'Registration only; pose anatomy requires visual review.'}
    (args.episode / cfg['report']).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
