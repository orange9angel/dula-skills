#!/usr/bin/env python3
"""beatcut-edit: music-driven rhythm-edit (卡点) video generator.

Reads a manifest describing sources (static images / cel-sequence dirs) and
optional expression frames, detects onsets in the music track, and compiles a
beat-synced edit: hard cuts, punch zoom, micro shake, RGB split, glitch
slices, white flash, blink-flutter pairs, reaction cut-ins, velocity ramp
around the drop (strongest onset).

Manifest (JSON):
{
  "sources": [{"type": "img"|"cels", "path": "..."}, ...],
  "expressions": ["expr1.png", ...],
  "blink_pair": ["open.png", "closed.png"],
  "voices": [{"t": 3.2, "file": "vo1.wav", "text": "口播台词"}, ...],
  "texts": [{"t": 0.5, "dur": 2.0, "text": "产品名", "pos": "top", "big": true}, ...],
  "sections": [{"until": 6.0, "density": 0.4}, {"until": 16.0, "density": 1.2}, ...]
}

voices = audible voiceover lines, mixed over the music with sidechain ducking,
plus a bottom subtitle while the line plays. texts = pop-in overlay copy.
sections = per-section effect density multipliers (default 1.0).

Usage:
  beatcut.py --manifest m.json --track track.wav --out out.mp4 \
      [--duration 22] [--fps 30] [--cut-every 2] [--rgb-every 4] \
      [--flash-every 8] [--seed 20260830]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageEnhance

W, H = 1920, 1080


def load_mono(path: Path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le",
                          "-ac", "1", "-ar", "44100", "-"],
                         capture_output=True, check=True).stdout
    return 44100, np.frombuffer(raw, dtype=np.float32)


def detect_onsets(samples: np.ndarray, sr: int):
    """Spectral-flux onsets -> [(t_seconds, strength)]."""
    hop, nfft = 512, 2048
    frames = [samples[i:i + nfft] for i in range(0, len(samples) - nfft, hop)]
    win = np.hanning(nfft)
    mags = np.abs(np.array([np.fft.rfft(f * win) for f in frames]))
    flux = np.maximum(0.0, np.diff(mags, axis=0)).sum(axis=1)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    thresh = np.percentile(flux, 90)
    min_gap = int(0.22 * sr / hop)
    out, last = [], -min_gap * 2
    for i in range(1, len(flux) - 1):
        if flux[i] > thresh and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] \
                and i - last >= min_gap:
            out.append((round(i * hop / sr, 4), float(flux[i])))
            last = i
    return out


class Source:
    def __init__(self, kind: str, path: Path):
        if kind == "cels":
            self.cels = [Image.open(p).convert("RGB") for p in sorted(path.glob("f_*.png"))]
            if not self.cels:
                raise ValueError(f"no cels in {path}")
            self.img = None
        else:
            self.img = Image.open(path).convert("RGB")
            self.cels = None

    def frame_at(self, local_t: float, fps: int = 12) -> Image.Image:
        if self.cels:
            return self.cels[min(len(self.cels) - 1, int(local_t * fps))]
        return self.img


def cover(img, scale, dx=0, dy=0, angle=0.0):
    w0, h0 = img.size
    s = max(W / w0, H / h0) * scale
    im = img.resize((round(w0 * s), round(h0 * s)), Image.LANCZOS)
    if abs(angle) > 0.01:
        im = im.rotate(angle, resample=Image.BICUBIC, center=(im.width / 2, im.height / 2))
    x = (im.width - W) // 2 + dx
    y = (im.height - H) // 2 + dy
    out = Image.new("RGB", (W, H), (10, 12, 30))
    region = im.crop((max(0, x), max(0, y), min(max(0, x) + W, im.width), min(max(0, y) + H, im.height)))
    out.paste(region, (max(0, -x), max(0, -y)))
    return out


def rgb_split(img, offset):
    r, g, b = img.split()
    return Image.merge("RGB", (ImageChops.offset(r, offset, 0), g,
                               ImageChops.offset(b, -offset, 0)))


def glitch(img, rng):
    out = img.copy()
    w, h = out.size
    for _ in range(3):
        y0 = int(rng.integers(0, h - 40))
        band_h = int(rng.integers(12, 42))
        shift = int(rng.integers(-90, 90))
        out.paste(ImageChops.offset(out.crop((0, y0, w, y0 + band_h)), shift, 0), (0, y0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--track", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--cut-every", type=int, default=2, help="hard cut every N beats")
    ap.add_argument("--rgb-every", type=int, default=4, help="RGB split every N beats")
    ap.add_argument("--flash-every", type=int, default=8, help="accent (flash/glitch + reaction) every N beats")
    ap.add_argument("--seed", type=int, default=20260830)
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    mroot = Path(args.manifest).parent

    sr, samples = load_mono(Path(args.track))
    onsets = [(t, s) for t, s in detect_onsets(samples, sr) if t <= args.duration]
    if len(onsets) < 4:
        print("ERROR: too few onsets", file=sys.stderr)
        return 1
    times = np.array([t for t, _ in onsets])
    strs = np.array([s for _, s in onsets])
    smax = float(strs.max())
    drop_t = float(times[int(strs.argmax())])
    beat_dur = float(np.median(np.diff(times))) if len(times) > 1 else 0.5
    print(f"onsets={len(onsets)}, drop@{drop_t:.2f}s, beat={beat_dur:.2f}s")

    sources = [Source(s["type"], (mroot / s["path"]).resolve()) for s in manifest["sources"]]
    # windowed sources: story-driven time windows take precedence over the
    # beat-rotation pool (ads are story-first, beat-second)
    windows = []
    for wspec in manifest.get("windows", []):
        windows.append({"t": float(wspec["t"]), "dur": float(wspec["dur"]),
                        "src": Source(wspec.get("type", "img"),
                                      (mroot / wspec["path"]).resolve())})
    windows.sort(key=lambda w: w["t"])
    exprs = [Image.open((mroot / p).resolve()).convert("RGB")
             for p in manifest.get("expressions", [])]
    blink_pair = None
    bp = manifest.get("blink_pair")
    if bp:
        blink_pair = [Image.open((mroot / bp[0]).resolve()).convert("RGB"),
                      Image.open((mroot / bp[1]).resolve()).convert("RGB")]
    print(f"sources={len(sources)}, expressions={len(exprs)}, blink_pair={bool(blink_pair)}")

    # voiceover lines + overlay copy + section densities
    voices = manifest.get("voices", [])
    for v in voices:
        vp = (mroot / v["file"]).resolve()
        dur_raw = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                  "format=duration", "-of", "csv=p=0", str(vp)],
                                 capture_output=True, text=True).stdout.strip()
        v["dur"] = float(dur_raw) if dur_raw else 2.0
        v["path"] = vp
    texts = manifest.get("texts", [])
    sections = sorted(manifest.get("sections", []), key=lambda s: s["until"])

    def density_at(t: float) -> float:
        for s in sections:
            if t < s["until"]:
                return float(s.get("density", 1.0))
        return float(sections[-1].get("density", 1.0)) if sections else 1.0

    def text_overlay(frame: Image.Image, t: float, active: list) -> Image.Image:
        if not active:
            return frame
        from PIL import ImageDraw, ImageFont
        frame = frame.copy()
        draw = ImageDraw.Draw(frame)
        font_cache = getattr(text_overlay, "cache", {})
        for x in active:
            size = int((86 if x.get("big") else 52))
            font = font_cache.get(size)
            if font is None:
                font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", size)
                font_cache[size] = font
            text_overlay.cache = font_cache
            elapsed = t - x["t"]
            pop = min(1.0, elapsed / 0.15)
            alpha_scale = 0.8 + 0.2 * pop
            bbox = draw.textbbox((0, 0), x["text"], font=font, stroke_width=3)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pos = x.get("pos", "bottom")
            cx = (W - tw) // 2
            cy = int(H * {"top": 0.12, "center": 0.42, "bottom": 0.78}[pos])
            layer = Image.new("RGBA", (tw + 80, th + 60), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.text((40, 20), x["text"], font=font, fill=(255, 255, 255, 255),
                    stroke_width=3, stroke_fill=(20, 20, 40, 255))
            nw, nh = int(layer.width * alpha_scale), int(layer.height * alpha_scale)
            layer = layer.resize((nw, nh), Image.LANCZOS)
            frame.paste(layer, (cx + (tw + 80 - nw) // 2, cy + (th + 60 - nh) // 2), layer)
        return frame

    rng = np.random.default_rng(args.seed)
    total = int(args.duration * args.fps)
    tmp = Path(args.out).with_suffix("")
    tmp.mkdir(parents=True, exist_ok=True)

    for f in range(total):
        t = f / args.fps
        bi = int(np.searchsorted(times, t, side="right")) - 1
        last_t, strength = (float(times[bi]), strs[bi]) if bi >= 0 else (0.0, 0.0)
        dt = t - last_t
        sn = strength / smax

        wsrc = None
        for wspec in windows:
            if wspec["t"] <= t < wspec["t"] + wspec["dur"]:
                wsrc = wspec["src"]
                break
        src = wsrc or sources[max(0, bi // args.cut_every) % len(sources)]
        if bi >= 0 and abs(t - drop_t) < 2 * beat_dur and t < drop_t:
            local_t = (t - last_t) * 0.5 + last_t
        elif 0 <= t - drop_t < 2 * beat_dur:
            local_t = (t - last_t) * 2.0 + last_t
        else:
            local_t = t
        img = src.frame_at(local_t)

        # expression play: blink flutter on the beat before an accent,
        # reaction frame on the accent itself
        if blink_pair and bi >= 0 and bi + 1 < len(times) and (bi + 1) % args.flash_every == 0:
            img = blink_pair[int((t - last_t) / (beat_dur / 2)) % 2]
        elif exprs and bi >= 0 and bi % args.flash_every == 0:
            img = exprs[(bi // args.flash_every) % len(exprs)]

        scale = 1.0 + 0.10 * sn * np.exp(-dt * 8.0) * density_at(t)
        shake = int(14 * sn * np.exp(-dt * 7.0) * density_at(t))
        dx = int(rng.integers(-shake, shake + 1)) if shake > 0 else 0
        dy = int(rng.integers(-shake, shake + 1)) if shake > 0 else 0
        angle = 0.8 * sn * np.exp(-dt * 6.0) * (1 if bi % 2 == 0 else -1)
        frame = cover(img, scale, dx, dy, angle)

        if bi >= 0 and bi % args.rgb_every == 0 and dt < 0.15:
            frame = rgb_split(frame, int(6 + 10 * sn))
        if bi >= 0 and bi % args.flash_every == 0 and dt < 0.13:
            frame = glitch(frame, rng) if bi % (2 * args.flash_every) == 0 else \
                ImageEnhance.Brightness(frame).enhance(1.0 + 1.8 * (1.0 - dt / 0.13))
        if abs(t - drop_t) < 0.10:
            frame = ImageEnhance.Color(frame).enhance(1.6)
            frame = rgb_split(frame, 12)
        # voiceover subtitle + overlay copy
        active = [x for x in texts if x["t"] <= t < x["t"] + x.get("dur", 2.0)]
        active += [{"t": v["t"], "dur": v["dur"], "text": v["text"],
                    "pos": "bottom", "big": False}
                   for v in voices if v["t"] <= t < v["t"] + v["dur"]]
        frame = text_overlay(frame, t, active)
        frame.save(tmp / f"f_{f:05d}.png")
        if f % 150 == 0:
            print(f"frame {f}/{total}", flush=True)

    # audio: voiceover lines delayed to their times, music sidechain-ducked
    # under the voice bus, then mixed.
    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(args.fps),
           "-i", str(tmp / "f_%05d.png"), "-i", args.track]
    if voices:
        fcx = []
        for i, v in enumerate(voices):
            cmd += ["-i", str(v["path"])]
            ms = int(round(v["t"] * 1000))
            fcx.append(f"[{i + 2}:a]adelay={ms}|{ms}[v{i}]")
        vo_in = "".join(f"[v{i}]" for i in range(len(voices)))
        fcx.append(f"{vo_in}amix=inputs={len(voices)}:normalize=0[vo]")
        fcx.append("[1:a][vo]sidechaincompress=threshold=0.03:ratio=6:attack=25:release=500[mduck]")
        fcx.append("[mduck][vo]amix=inputs=2:normalize=0[aout]")
    else:
        fcx = ["[1:a]anull[aout]"]
    cmd += ["-filter_complex", ";".join(fcx), "-map", "0:v", "-map", "[aout]",
            "-t", str(args.duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", args.out]
    subprocess.run(cmd, check=True)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
