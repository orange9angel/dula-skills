#!/usr/bin/env python3
"""Generate or edit one image via Codex CLI built-in imagegen (gpt-image).

Default zero-marginal-cost provider for lightweight single artifacts (style
tests, character/scene masters, one-off keyframes, mouth/eye/leg local-edit
variants). Bills against the ChatGPT subscription quota, not API cash.

The paid DashScope/Bailian path (gen_image.py, wan2.7-image-pro) is the
automatic fallback for codex quota exhaustion (2026-08, user decision);
gen_image_auto.py implements the codex-first chain. Direct gen_image.py use
is still appropriate when structured API knobs (seed, mask, negative prompt)
are truly required.

Usage:
  python gen_image_codex.py --out <episode>/assets/keyframes/frame_00.png \
      --ref <episode>/assets/style_master.png --ref <episode>/assets/scene.png \
      --prompt "Use case: establishing shot ... <style hardLock> <avoid list>" \
      [--prompt-file prompt.txt] [--size 1672x941] [--overwrite] [--timeout 600]

Reference order is weight order: identity master first, nearest approved frame
next. Local-edit variants: pass only the base frame as --ref with an
instruction prompt ("change only the mouth to half-open; every other pixel
unchanged"), then diff-check and feather-lock with the episode's lock tool.

Hard-won rules encoded here (references/codex-cli-imagegen.md):
- prompt is a positional arg BEFORE any -i flags (else codex eats it as a file)
- never ask codex to save into the project: its Windows save path can silently
  fail; we harvest ~/.codex/generated_images/<session-id>/ ourselves instead
- run serially, foreground only; one call per process
- per-frame size must go into the prompt when editing (mixed sizes per episode)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

GENERATED_ROOT = Path.home() / ".codex" / "generated_images"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, type=Path, help="Destination PNG path")
    p.add_argument("--ref", action="append", default=[], help="Reference image (repeatable; order = weight)")
    p.add_argument("--prompt", help="Inline prompt text")
    p.add_argument("--prompt-file", type=Path, help="Read prompt from file instead")
    p.add_argument("--size", help="Expected WxH, e.g. 1672x941; resizes via PIL when mismatched")
    p.add_argument("--overwrite", action="store_true", help="Allow replacing an existing --out")
    p.add_argument("--timeout", type=int, default=600, help="codex exec timeout in seconds (default 600)")
    args = p.parse_args()
    if not args.prompt and not args.prompt_file:
        p.error("one of --prompt / --prompt-file is required")
    return args


def build_prompt(args: argparse.Namespace) -> str:
    prompt = args.prompt or args.prompt_file.read_text(encoding="utf-8")
    roles = []
    for i, _ in enumerate(args.ref, start=1):
        roles.append(f"image {i}" if i == 1 else f"image {i}")
    if args.ref:
        prompt += (
            "\n\nReference images attached in weight order: "
            + ", ".join(roles)
            + ". Match the earliest images for identity/style, later ones for staging."
        )
    if args.size:
        prompt += f"\nOutput exact pixel size: {args.size}."
    prompt += "\nGenerate the image with your image tool. Do NOT save or move any files yourself."
    return prompt


def main() -> None:
    args = parse_args()
    if args.out.exists() and not args.overwrite:
        sys.exit(f"refusing to overwrite existing {args.out} (pass --overwrite)")

    prompt = build_prompt(args)
    codex_exe = shutil.which("codex") or "codex"
    cmd = [
        codex_exe, "exec", prompt,
        "--skip-git-repo-check", "--ephemeral", "-s", "workspace-write",
    ]
    for ref in args.ref:
        cmd += ["-i", str(Path(ref).resolve())]
    if os.name == "nt" and codex_exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", *cmd]  # npm shim: needs the cmd interpreter

    before = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        sys.exit(f"codex exec failed ({proc.returncode}):\n{log[-3000:]}")

    m = re.search(r"session id:\s*([0-9a-f-]+)", log, re.IGNORECASE)
    candidates = []
    if m:
        session_dir = GENERATED_ROOT / m.group(1)
        candidates = sorted(session_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    if not candidates:  # fallback: newest png created during this run
        candidates = sorted(
            (p for p in GENERATED_ROOT.glob("*/*.png") if p.stat().st_mtime >= before - 5),
            key=lambda p: p.stat().st_mtime,
        )
    if not candidates:
        sys.exit(f"no generated image found under {GENERATED_ROOT}:\n{log[-3000:]}")

    src = candidates[-1]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, args.out)

    note = ""
    if args.size:
        want_w, want_h = (int(v) for v in args.size.lower().split("x"))
        try:
            from PIL import Image
            with Image.open(args.out) as im:
                got = im.size
                if got != (want_w, want_h):
                    im.resize((want_w, want_h), Image.LANCZOS).save(args.out)
                    note = f" (resized {got[0]}x{got[1]} -> {want_w}x{want_h})"
        except ImportError:
            note = " (PIL unavailable; size not verified)"
    print(f"OK {args.out}{note} <- {src}")


if __name__ == "__main__":
    main()
