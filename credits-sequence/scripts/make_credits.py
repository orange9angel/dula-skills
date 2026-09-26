#!/usr/bin/env python3
"""credits-sequence — 漫威式片尾生成器（零生成费，纯程序化）。
输入:
  --images img1.png img2.png ...   蒙太奇底图（未采用素材）
  --audio song.mp3                 片尾曲（自动裁到目标时长+淡出）
  --credits credits.json           演职员表 [{role, name}, ...]
  --duration 30                    总时长（默认 30s）
  --out credits.mp4
结构: Ken Burns 缓推蒙太奇 + xfade/光闪转场 + 右侧竖栏滚动演职员表。
依赖: PIL + numpy + ffmpeg（无 AI 生成调用）。
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1280, 720
FPS = 24
FONT_ROLE = "C:/Windows/Fonts/msyhl.ttc"
FONT_NAME = "C:/Windows/Fonts/STKAITI.TTF"


def ken_burns(img: Image.Image, n_frames: int, zoom_dir: int) -> list[Image.Image]:
    """每张图 1.0→1.08（或反向）缓推，输出帧序列。"""
    im = img.convert("RGB").resize((W, H), Image.LANCZOS)
    frames = []
    for n in range(n_frames):
        p = n / max(1, n_frames - 1)
        z = 1.0 + 0.08 * p if zoom_dir > 0 else 1.08 - 0.08 * p
        cw, ch = int(W / z), int(H / z)
        x0 = (W - cw) // 2
        y0 = (H - ch) // 2
        frames.append(im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.LANCZOS))
    return frames


def render_credits_strip(credits: list[dict], strip_h: int) -> Image.Image:
    """右侧竖栏滚动内容（整张长条 PNG，RGBA）。"""
    w = 460
    im = Image.new("RGBA", (w, strip_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fr = ImageFont.truetype(FONT_ROLE, 30)
    fn = ImageFont.truetype(FONT_NAME, 42)
    y = 40
    for c in credits:
        d.text((30, y), c["role"], font=fr, fill=(150, 160, 168, 255))
        y += 44
        d.text((30, y), c["name"], font=fn, fill=(232, 236, 238, 255))
        y += 92
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="+", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--credits", required=True)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    work = out.parent / "_credits_tmp"
    work.mkdir(parents=True, exist_ok=True)
    total_frames = int(args.duration * FPS)

    images = [Image.open(p) for p in args.images]
    per = total_frames // len(images)
    xfade_frames = int(0.6 * FPS)  # 交叉淡化 0.6s

    # 1. 生成蒙太奇帧序列（Ken Burns + 交叉淡化拼接 + 中段一次光闪）
    # 注意：xfade 重叠会消耗帧数（N-1 段过渡各吃掉 xfade 帧），
    # 所以每段多生成 xfade 帧补偿，末尾裁回 total_frames。
    seq: list[Image.Image] = []
    for i, img in enumerate(images):
        n = per if i < len(images) - 1 else total_frames - per * (len(images) - 1)
        zb = ken_burns(img, n + xfade_frames, 1 if i % 2 == 0 else -1)
        if i == 0:
            seq.extend(zb)
        else:
            prev_tail = seq[-xfade_frames:]
            head = zb[:xfade_frames]
            blend = [
                Image.blend(prev_tail[k], head[k], (k + 1) / (xfade_frames + 1))
                for k in range(xfade_frames)
            ]
            seq[-xfade_frames:] = blend
            seq.extend(zb[xfade_frames:])
    seq = seq[:total_frames]
    # 中段光闪转场（第 1/2 处，2 帧白闪）
    mid = len(seq) // 2
    seq[mid] = Image.blend(seq[mid], Image.new("RGB", (W, H), (255, 255, 255)), 0.85)
    seq[mid + 1] = Image.blend(seq[mid + 1], Image.new("RGB", (W, H), (255, 255, 255)), 0.45)

    # 2. 演职员表长条
    credits = json.loads(Path(args.credits).read_text(encoding="utf-8"))
    strip_h = 40 + len(credits) * 136 + 80
    strip = render_credits_strip(credits, strip_h)
    scroll_range = H + strip_h
    v_per_frame = scroll_range / total_frames

    # 3. 逐帧合成：右栏暗渐变 + 滚动字幕
    grad = Image.new("L", (460, H), 0)
    gd = ImageDraw.Draw(grad)
    for x in range(460):
        gd.line([(x, 0), (x, H)], fill=int(150 * (x / 460)))
    dark = Image.new("RGBA", (460, H), (5, 8, 10, 255))

    frames_dir = work / "frames"
    frames_dir.mkdir(exist_ok=True)
    for n, base in enumerate(seq):
        im = base.convert("RGBA")
        panel = Image.composite(dark, Image.new("RGBA", (460, H), (0, 0, 0, 0)), grad)
        im.paste(panel, (W - 460, 0), panel)
        y = int(H - n * v_per_frame)
        im.paste(strip, (W - 460, y), strip)
        im.convert("RGB").save(frames_dir / f"f_{n:05d}.png")

    # 4. 音频裁剪+淡出，合成
    aud = work / "song.wav"
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-i", args.audio,
        "-t", str(args.duration),
        "-af", f"afade=t=out:st={args.duration - 2.5}:d=2.5", str(aud),
    ], check=True)
    silent = work / "silent.mp4"
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS),
        "-i", str(frames_dir / "f_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(silent),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(aud),
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out),
    ], check=True)
    print(f"credits: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
