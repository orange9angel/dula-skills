"""Compare a revised complete-cel sequence against an existing exposure report.

The drawing schedule is shared by both panels. No interpolation or limb rigging.
An isolated tracking portrait does not validate world-space foot contacts.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--episode', type=Path, required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    root = args.episode
    config = json.loads((root / args.config).read_text(encoding='utf-8'))
    exposure = json.loads((root / config['exposure']).read_text(encoding='utf-8'))['exposure']
    output = root / config['output']
    for name in ['frames', 'revised']:
        (output / name).mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(config['font'], 22)
    small = ImageFont.truetype(config['font'], 16)
    cache = {}
    for row in exposure:
        key = row['key']
        if key in cache:
            continue
        revised_key = config.get('aliases', {}).get(key, key)
        before = Image.open(root / config['before'] / (key + '.png')).convert('RGB')
        rgba = Image.open(root / config['after'] / (revised_key + '.png')).convert('RGBA')
        after = Image.new('RGB', rgba.size, tuple(config.get('background', [128, 136, 144])))
        after.paste(rgba, (0, 0), rgba)
        if before.size != after.size:
            raise ValueError('Comparison panel sizes must agree')
        cache[key] = before, after
    for row in exposure:
        before, after = cache[row['key']]
        w, h = after.size
        frame = Image.new('RGB', (w * 2, h + 74), '#18212f')
        frame.paste(before, (0, 44))
        frame.paste(after, (w, 44))
        draw = ImageDraw.Draw(frame)
        for column, label in enumerate(config['labels']):
            draw.text((column * w + 12, 10), label, font=font, fill='white')
        draw.text((12, h + 49), f"{row['t']:.3f}s / {row['key']} / " + config['footer'], font=small, fill='#ffcf8a')
        tag = f"{row['i']:04d}.png"
        frame.save(output / 'frames' / tag, compress_level=2)
        after.save(output / 'revised' / tag, compress_level=2)
    # Ordered complete drawings, at useful inspection size.
    ids = list(dict.fromkeys(row['key'] for row in exposure if row['key'] not in config.get('aliases', {})))
    cols = 4
    sheet = Image.new('RGB', (cols * w, ((len(ids) + cols - 1) // cols) * (h + 28)), '#808890')
    draw = ImageDraw.Draw(sheet)
    for index, key in enumerate(ids):
        x, y = index % cols * w, index // cols * (h + 28)
        sheet.paste(cache[key][1], (x, y + 28))
        draw.text((x + 10, y + 4), key, font=small, fill='white')
    sheet.save(output / 'ordered_cels.jpg', quality=94)
    (output / 'report.json').write_text(json.dumps({
        'config': config, 'exposure': exposure, 'frames': len(exposure),
        'scope': 'Same exposure, complete drawings. No world-contact or smooth-motion claim.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'frames': len(exposure), 'output': str(output)}))


if __name__ == '__main__':
    main()
