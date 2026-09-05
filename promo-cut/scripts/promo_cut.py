#!/usr/bin/env python3
"""promo-cut: cut a finished episode (正片) into a 15-30s beat-synced promo (广告片).

One command: reads config/keyframe_timeline.json, picks shot windows heuristically
(omni talking shots / i2v action / finale wide), aligns hard cuts to BGM onsets
(reusing load_mono/detect_onsets from beatcut-edit), inserts a freeze-frame with
slow push-in + white flash + synthesized shutter click every N beats, prepends a
flat-color title card (sunprint palette), and renders straight to mp4.
No GUI, deps = numpy + PIL + ffmpeg only.

Usage:
  promo_cut.py <episode_dir> --music bgm.wav --out promo.mp4 --duration 20 \
      --title "猫带我去的地方" --subtitle "E06 模特小橘"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# reuse beat detection from beatcut-edit (no code duplication)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                     / "beatcut-edit" / "scripts"))
from beatcut import load_mono, detect_onsets  # noqa: E402

W, H = 1920, 1080
SR = 44100

# sunprint palette (晴印色板)
BG_COLOR = (46, 155, 214)      # 深青蓝 #2E9BD6
TITLE_COLOR = (245, 185, 66)   # 阳光金 #F5B942
SUB_COLOR = (253, 251, 244)    # 云白 #FDFBF4


# ---------------------------------------------------------------- timeline ---

def shot_base(shot: str) -> str:
    return re.sub(r"_\d+$", "", shot)


def load_segments(episode_dir: Path):
    """Aggregate keyframe_timeline frames into contiguous shot segments.

    Returns list of dicts: {name, kind(omni|i2v|static), start, end}.
    """
    tl = json.loads((episode_dir / "config" / "keyframe_timeline.json")
                    .read_text(encoding="utf-8"))
    total = float(tl.get("duration", 60.0))
    segs = []
    for f in tl["frames"]:
        base = shot_base(f["shot"])
        if segs and segs[-1]["name"] == base:
            continue
        path = f.get("file", "")
        kind = "omni" if path.startswith("omni/") else \
               "i2v" if path.startswith("i2v/") else "static"
        segs.append({"name": base, "kind": kind, "start": float(f["at"])})
    for i, s in enumerate(segs):
        s["end"] = segs[i + 1]["start"] if i + 1 < len(segs) else total
    return segs


def pick_windows(segs):
    """Heuristic candidate windows, best-first.

    omni talking shots (skip first 0.3s breath) -> i2v action -> finale wide.
    Returns (candidates, finale) where each window is (start, end).
    """
    cands = []
    finale = None
    for s in segs:
        dur = s["end"] - s["start"]
        name = s["name"].lower()
        if "finale" in name or "wide" in name:
            if "fade" not in name and dur >= 2.0:
                w = (s["start"] + 0.5, s["end"] - 0.5)
                if finale is None or (w[1] - w[0]) > (finale[1] - finale[0]):
                    finale = w
            continue
        if s["kind"] == "omni" and dur >= 1.5:
            cands.append((s["start"] + 0.3, s["end"] - 0.1))
        elif s["kind"] == "i2v" and dur >= 1.0:
            cands.append((s["start"] + 0.1, s["end"] - 0.1))
    return cands, finale


# ------------------------------------------------------------------- audio ---

def synth_shutter(dur=0.15):
    """20ms noise pulse + short 2kHz sine, camera-shutter-ish."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(7).standard_normal(n).astype(np.float32)
    noise *= (t < 0.02) * np.exp(-t * 120.0)
    tone = np.sin(2 * np.pi * 2000 * t).astype(np.float32) * np.exp(-t * 45.0)
    return 0.5 * noise + 0.3 * tone


def write_wav(path: Path, samples: np.ndarray):
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def build_audio(music: Path, duration: float, shutter_times, out_wav: Path):
    sr, samples = load_mono(music)
    n = int(duration * sr)
    mix = samples[:n].copy()
    if len(mix) < n:
        mix = np.pad(mix, (0, n - len(mix)))
    peak = np.abs(mix).max()
    if peak > 0:
        mix *= 0.85 / peak
    click = synth_shutter()
    for st in shutter_times:
        i = int(st * sr)
        j = min(n, i + len(click))
        mix[i:j] += click[:j - i]
    peak = np.abs(mix).max()
    if peak > 0.95:  # clicks can push the mix over full scale; re-normalize
        mix *= 0.95 / peak
    write_wav(out_wav, mix)


# ------------------------------------------------------------------- video ---

def grab_frames(src: Path, start: float, dur: float) -> np.ndarray:
    """Decode [start, start+dur] of src to (n, H, W, 3) uint8 via rawvideo."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.4f}", "-i", str(src),
         "-t", f"{dur:.4f}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True).stdout
    n = len(raw) // (W * H * 3)
    if n == 0:
        raise RuntimeError(f"no frames at {start:.2f}s in {src}")
    return np.frombuffer(raw[:n * W * H * 3], dtype=np.uint8).reshape(n, H, W, 3)


def grab_frame(src: Path, t: float) -> Image.Image:
    return Image.fromarray(grab_frames(src, t, 0.05)[0])


def cover(img: Image.Image, scale: float) -> Image.Image:
    w0, h0 = img.size
    s = max(W / w0, H / h0) * scale
    im = img.resize((round(w0 * s), round(h0 * s)), Image.LANCZOS)
    x = (im.width - W) // 2
    y = (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def load_font(size: int):
    for cand in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if Path(cand).exists():
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def title_card(title: str, subtitle: str):
    """Return (bg_image, text_layer_rgba) — fade-in is applied to the layer."""
    bg = Image.new("RGB", (W, H), BG_COLOR)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if title:
        f = load_font(120)
        bb = d.textbbox((0, 0), title, font=f)
        d.text(((W - (bb[2] - bb[0])) // 2, int(H * 0.38)), title,
               font=f, fill=TITLE_COLOR + (255,))
    if subtitle:
        f = load_font(56)
        bb = d.textbbox((0, 0), subtitle, font=f)
        d.text(((W - (bb[2] - bb[0])) // 2, int(H * 0.60)), subtitle,
               font=f, fill=SUB_COLOR + (255,))
    return bg, layer


def fade_paste(bg: Image.Image, layer: Image.Image, alpha: float) -> Image.Image:
    out = bg.copy()
    if alpha >= 1.0:
        out.paste(layer, (0, 0), layer)
    else:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        out.paste(layer, (0, 0), a)
    return out


# -------------------------------------------------------------------- main ---

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--music", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--title-dur", type=float, default=2.0)
    ap.add_argument("--cut-every", type=int, default=2, help="hard cut every N beats")
    ap.add_argument("--freeze-every", type=int, default=8, help="freeze every N beats")
    ap.add_argument("--freeze-dur", type=float, default=1.0)
    args = ap.parse_args()

    ep = Path(args.episode_dir)
    outdir = ep / "output"
    srcs = sorted(outdir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    srcs = [p for p in srcs if p.resolve() != Path(args.out).resolve()]
    if not srcs:
        print("ERROR: no source mp4 in output/", file=sys.stderr)
        return 1
    src = srcs[-1]
    src_dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip())
    print(f"source: {src.name} ({src_dur:.1f}s)")

    segs = load_segments(ep)
    cands, finale = pick_windows(segs)
    if not cands:
        print("ERROR: no candidate windows", file=sys.stderr)
        return 1
    print(f"windows: {len(cands)} candidates, finale={finale}")

    # beat grid from BGM
    _, samples = load_mono(Path(args.music))
    onsets = [t for t, _ in detect_onsets(samples, SR)]
    cuts = [t for t in onsets[::args.cut_every]
            if args.title_dur <= t < args.duration - 0.3]
    if len(cuts) < 3:
        print("ERROR: too few cut beats", file=sys.stderr)
        return 1

    # EDL: video entries {a,b,ws}; freeze entries {a,b,ws(freeze at),kind}
    edl = []
    ci = 0  # candidate cursor
    for i, b0 in enumerate(cuts):
        b1 = cuts[i + 1] if i + 1 < len(cuts) else args.duration
        ws, we = cands[ci % len(cands)]
        cur = ws + (ci // len(cands)) * 0.4  # advance a bit on wrap
        cur = min(cur, we - 0.3)
        ci += 1
        is_freeze = (i + 1) * args.cut_every % args.freeze_every == 0
        if is_freeze and b1 - b0 > args.freeze_dur + 0.2:
            edl.append({"kind": "freeze", "a": b0, "b": b0 + args.freeze_dur,
                        "ws": cur})
            edl.append({"kind": "video", "a": b0 + args.freeze_dur, "b": b1,
                        "ws": cur})
        elif is_freeze:
            edl.append({"kind": "freeze", "a": b0, "b": b1, "ws": cur})
        else:
            edl.append({"kind": "video", "a": b0, "b": b1, "ws": cur})
    # ending lands on the finale wide: reroute the last ~2s of video entries
    if finale:
        tail = args.duration - 2.0
        for e in edl:
            if e["kind"] == "video" and e["b"] > tail:
                e["ws"] = finale[0] + max(0.0, e["a"] - tail) * 0.3
    edl = [e for e in edl if e["ws"] + 0.05 < src_dur]
    shutter_times = [e["a"] for e in edl if e["kind"] == "freeze"]
    print(f"edl: {len(edl)} entries, freezes at "
          f"{[round(t, 2) for t in shutter_times]}")

    # decode windows per entry (short clips, decoded once)
    for e in edl:
        arr = grab_frames(src, e["ws"], e["b"] - e["a"] + 0.1)
        e["frames"] = arr
        if e["kind"] == "freeze":
            e["still"] = Image.fromarray(arr[0])

    # audio bed: BGM trimmed + shutter clicks
    tmp = Path(args.out).with_suffix("").parent / (Path(args.out).stem + "_work")
    tmp.mkdir(parents=True, exist_ok=True)
    wav = tmp / "mix.wav"
    build_audio(Path(args.music), args.duration, shutter_times, wav)

    # render frames
    bg, layer = title_card(args.title, args.subtitle)
    total = int(args.duration * args.fps)
    ei = 0
    for f in range(total):
        t = f / args.fps
        if t < args.title_dur:
            alpha = min(1.0, t / 0.3)
            frame = fade_paste(bg, layer, alpha)
        else:
            while ei + 1 < len(edl) and t >= edl[ei]["b"]:
                ei += 1
            e = edl[ei]
            local = t - e["a"]
            if e["kind"] == "freeze":
                scale = 1.0 + 0.08 * min(1.0, local / args.freeze_dur)
                frame = cover(e["still"], scale)
                if local < 0.1:  # white flash at freeze start
                    white = Image.new("RGB", (W, H), (255, 255, 255))
                    frame = Image.blend(frame, white, 0.85 * (1 - local / 0.1))
            else:
                idx = min(len(e["frames"]) - 1, int(local * args.fps))
                frame = Image.fromarray(e["frames"][idx])
        frame.save(tmp / f"f_{f:05d}.png")
        if f % 150 == 0:
            print(f"frame {f}/{total}", flush=True)

    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-framerate", str(args.fps),
         "-i", str(tmp / "f_%05d.png"), "-i", str(wav),
         "-map", "0:v", "-map", "1:a", "-t", str(args.duration),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", args.out], check=True)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
