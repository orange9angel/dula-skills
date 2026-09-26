#!/usr/bin/env python3
"""《9章》转场卡 v3 —— 水墨侵蚀光效字 + 光效版。
两张卡:
  mid  : bg=cut_16.3.png  副标「残卷 · 其一」  出场白光爆发
  end  : bg=assets/keyframes/frame_10.png  副标「序章 · 完」  收尾淡黑
标题工艺: STKAITI 楷体 + numpy 噪声场阈值侵蚀（字从墨韵中长出）+
          前沿青绿辉光 + 飞白干笔纹理 + 光扫/光斑。
产物: tmp/transition/frames_mid/, tmp/transition/frames_end/
"""
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter, zoom

W, H = 1280, 720
FPS = 24
ROOT = Path(__file__).resolve().parents[1]
FONT_TITLE = "C:/Windows/Fonts/STKAITI.TTF"
FONT_SUB = "C:/Windows/Fonts/STKAITI.TTF"

TEAL = np.array([61, 255, 200], dtype=np.float32)
AMBER = np.array([245, 184, 90], dtype=np.float32)
INK = np.array([252, 244, 230], dtype=np.float32)

random.seed(9)


def make_noise(seed, base=(180, 320)):
    rng = np.random.default_rng(seed)
    acc = np.zeros(base, np.float32)
    wsum = 0.0
    for s, w in [(2, 1.0), (6, 0.6), (16, 0.35)]:
        acc += gaussian_filter(rng.random(base).astype(np.float32), s) * w
        wsum += w
    acc /= wsum
    acc = zoom(acc, (4, 4), order=1)[:H, :W]
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-9)


def text_mask(text, size, y_ratio=0.30, blur=1.2):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT_TITLE, size)
    tw = d.textlength(text, font=f)
    d.text(((W - tw) / 2, H * y_ratio), text, font=f, fill=255)
    m = np.asarray(im.filter(ImageFilter.GaussianBlur(blur)), dtype=np.float32) / 255.0
    return m, f


class InkTitle:
    def __init__(self, text, size=200, y_ratio=0.30, seed=7):
        self.mask, _ = text_mask(text, size, y_ratio)
        noise = make_noise(seed)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        radial = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.42) / (H * 0.62)) ** 2)
        radial = np.clip(radial / radial.max(), 0, 1)
        self.field = 0.65 * noise + 0.35 * radial
        self.fine = make_noise(seed + 99)

    def frame(self, p):
        """p: 0→1 墨韵侵蚀进度。返回 (alpha, frontier, drybrush)"""
        soft = np.clip((p * 1.3 - self.field) * 10.0, 0, 1)
        alpha = soft * self.mask
        frontier = np.clip(soft * (1 - soft) * 4.0, 0, 1) * np.clip(self.mask * 3, 0, 1)
        dry = np.clip(0.72 + 0.5 * (self.fine - 0.5) * 2, 0, 1)
        return alpha * dry, frontier, dry


def bg_frame(src_img, t, total, blur=6, bright=0.6, zoom_to=1.06):
    z = 1.0 + (zoom_to - 1.0) * (t / total)
    cw, ch = int(W / z), int(H / z)
    x0, y0 = (W - cw) // 2, (H - ch) // 2
    im = src_img.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(blur))
    return ImageEnhance.Brightness(im).enhance(bright)


BOKEH = [
    (random.uniform(0, W), random.uniform(H * 0.3, H), random.uniform(-8, 8), random.uniform(-30, -10),
     random.uniform(6, 26), random.choice([(61, 255, 200), (245, 184, 90), (250, 250, 246)]), random.uniform(0.3, 0.9))
    for _ in range(40)
]


def composite_ink(bg_rgb: np.ndarray, alpha: np.ndarray, frontier: np.ndarray, strength=1.0):
    out = bg_rgb.astype(np.float32)
    a = (alpha * strength)[..., None]
    f = (frontier * strength)[..., None]
    # 前沿辉光（screen 叠加）
    glow = frontier[..., None] * TEAL
    out = 255 - (255 - out) * (255 - np.clip(glow, 0, 255)) / 255
    out = out * (1 - a) + INK * a
    return np.clip(out, 0, 255).astype(np.uint8)


def light_sweep(im: Image.Image, t, t0=0.3, t1=0.8):
    if not (t0 <= t < t1):
        return im
    p = (t - t0) / (t1 - t0)
    sweep = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dsw = ImageDraw.Draw(sweep)
    cx = -300 + (W + 600) * p
    dsw.polygon([(cx - 180, H), (cx - 60, 0), (cx + 60, 0), (cx - 60, H)],
                fill=(255, 255, 255, int(110 * math.sin(math.pi * p))))
    sweep = sweep.filter(ImageFilter.GaussianBlur(40))
    return Image.alpha_composite(im, sweep)


def bokeh(im: Image.Image, pt):
    if pt <= 0:
        return im
    bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    db = ImageDraw.Draw(bok)
    for px, py, vx, vy, r, col, k in BOKEH:
        x, y = px + vx * pt, py + vy * pt
        a = int(150 * k * min(1.0, pt * 1.5))
        db.ellipse((x - r, y - r, x + r, y + r), fill=(*col, a))
    bok = bok.filter(ImageFilter.GaussianBlur(6))
    return Image.alpha_composite(im, bok)


def subtitle(im: Image.Image, text, a):
    st = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(st)
    f = ImageFont.truetype(FONT_SUB, 42)
    sw = ds.textlength(text, font=f)
    ds.text(((W - sw) / 2, H * 0.68), text, font=f, fill=(215, 222, 226, int(210 * a)))
    return Image.alpha_composite(im, st)


def render_card(bg_path, sub, out_dir, n_frames, ink: InkTitle,
                reveal=(0.18, 0.66), dissolve_out=True, fade_black=False):
    src = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = n_frames / FPS
    for n in range(n_frames):
        t = n / FPS
        bg = bg_frame(src, t, total)
        # 墨韵进度
        if t < reveal[0]:
            p = 0.0
        elif t < reveal[1]:
            q = (t - reveal[0]) / (reveal[1] - reveal[0])
            p = 1 - (1 - q) ** 3
        else:
            p = 1.0
        if dissolve_out and t >= total - 0.28:
            p = max(0.0, 1.0 - (t - (total - 0.28)) / 0.28 * 1.4)
        alpha, frontier, _ = ink.frame(p)
        arr = composite_ink(np.asarray(bg), alpha, frontier, strength=min(1.0, p * 3 + 0.2))
        im = Image.fromarray(arr).convert("RGBA")
        im = light_sweep(im, t)
        im = bokeh(im, t - 0.4)
        if t > reveal[1]:
            im = subtitle(im, sub, min(1.0, (t - reveal[1]) / 0.25))
        im = im.convert("RGB")
        # 注意：ImageDraw 在 RGBA 画布上是像素替换而非混合，淡入淡出必须走 blend
        if t < 0.15:
            im = Image.blend(im, Image.new("RGB", (W, H), (255, 255, 255)), 1 - t / 0.15)
        if dissolve_out and t >= total - 0.28:
            q = (t - (total - 0.28)) / 0.28
            im = Image.blend(im, Image.new("RGB", (W, H), (255, 255, 255)), min(1.0, q * q))
        if fade_black and t >= total - 0.45:
            q = (t - (total - 0.45)) / 0.45
            im = ImageEnhance.Brightness(im).enhance(max(0.0, 1 - q))
        im.save(out_dir / f"f_{n:03d}.png")
    print(f"{out_dir}: {n_frames} frames")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="程序化转场字卡（墨韵侵蚀标题 + 光效）")
    ap.add_argument("--bg", required=True, help="底图路径")
    ap.add_argument("--title", required=True, help="标题文字（如 9章）")
    ap.add_argument("--subtitle", default="", help="副标（如 残卷 · 其一）")
    ap.add_argument("--title-size", type=int, default=200)
    ap.add_argument("--title-y", type=float, default=0.30, help="标题纵位（画面比例）")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--duration", type=float, default=1.2, help="秒")
    ap.add_argument("--reveal", default="0.18,0.62", help="墨韵侵蚀起止（秒,秒）")
    ap.add_argument("--out-mode", choices=["white", "black"], default="white",
                    help="出场方式：白光爆发 / 淡黑")
    ap.add_argument("--out-dir", required=True, help="帧序列输出目录")
    args = ap.parse_args()

    r0, r1 = (float(x) for x in args.reveal.split(","))
    ink = InkTitle(args.title, args.title_size, args.title_y, seed=args.seed)
    render_card(
        Path(args.bg), args.subtitle, Path(args.out_dir),
        int(round(args.duration * FPS)), ink,
        reveal=(r0, r1),
        dissolve_out=(args.out_mode == "white"),
        fade_black=(args.out_mode == "black"),
    )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
