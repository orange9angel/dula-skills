#!/usr/bin/env python3
"""Provider chain: Codex built-in imagegen first, DashScope/Bailian fallback.

Policy (2026-08, user decision): codex imagegen bills against the ChatGPT
subscription quota (zero marginal cost), so it is always tried first. Only
when codex reports a usage/quota/rate limit do we fall back to the paid
DashScope path (gen_image.py, wan2.7-image-pro) automatically.

Interface mirrors gen_image_codex.py; extra knobs control the fallback leg.

Usage:
  python gen_image_auto.py --out <episode>/assets/keyframes/frame_00.png \
      --ref <episode>/assets/style_master.png \
      --prompt "Use case: establishing shot ... <style hardLock> <avoid list>" \
      [--size 1672x941] [--overwrite] [--timeout 600] \
      [--provider auto|codex|dashscope] [--dashscope-size 2K]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GEN_CODEX = SCRIPT_DIR / "gen_image_codex.py"
GEN_DASHSCOPE = SCRIPT_DIR / "gen_image.py"

# Output fragments that mean "codex quota is gone, do not retry codex".
QUOTA_PATTERNS = re.compile(
    r"usage.?limit|rate.?limit|quota|usage_limit|\b429\b|too many requests",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--ref", action="append", default=[], help="repeatable; order = weight")
    p.add_argument("--prompt")
    p.add_argument("--prompt-file", type=Path)
    p.add_argument("--size", help="codex size WxH, e.g. 1672x941")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--provider", choices=["auto", "codex", "dashscope"], default="auto",
                   help="auto = codex first, dashscope on quota failure (default)")
    p.add_argument("--dashscope-model", default="wan2.7-image-pro")
    p.add_argument("--dashscope-size", default="2K", help="fallback size token 1K/2K/4K")
    args = p.parse_args()
    if not args.prompt and not args.prompt_file:
        p.error("one of --prompt / --prompt-file is required")
    return args


def run(script: Path, argv: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run([sys.executable, str(script), *argv],
                          capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    for line in output.splitlines():
        print(f"   {line}", flush=True)
    return subprocess.CompletedProcess(proc.args, proc.returncode, output, "")


def codex_argv(args: argparse.Namespace) -> list[str]:
    argv = ["--out", str(args.out)]
    for ref in args.ref:
        argv += ["--ref", ref]
    if args.prompt_file:
        argv += ["--prompt-file", str(args.prompt_file)]
    else:
        argv += ["--prompt", args.prompt]
    if args.size:
        argv += ["--size", args.size]
    if args.overwrite:
        argv.append("--overwrite")
    argv += ["--timeout", str(args.timeout)]
    return argv


def dashscope_argv(args: argparse.Namespace) -> list[str]:
    argv = ["--out", str(args.out)]
    for ref in args.ref:
        argv += ["--ref", ref]
    if args.prompt_file:
        argv += ["--prompt-file", str(args.prompt_file)]
    else:
        argv += ["--prompt", args.prompt]
    argv += ["--model", args.dashscope_model, "--size", args.dashscope_size]
    if args.overwrite:
        argv.append("--overwrite")
    return argv


def main() -> int:
    args = parse_args()

    if args.provider in ("auto", "codex"):
        print(f"== codex -> {args.out}", flush=True)
        result = run(GEN_CODEX, codex_argv(args))
        if result.returncode == 0 and args.out.is_file():
            return 0
        quota_hit = bool(QUOTA_PATTERNS.search(result.stdout or ""))
        if args.provider == "codex" or not quota_hit:
            print(f"== codex failed ({'quota' if quota_hit else 'error'}); "
                  "no fallback", file=sys.stderr, flush=True)
            return result.returncode or 1
        print("== codex quota/rate limit hit; falling back to DashScope (paid)",
              flush=True)

    print(f"== dashscope -> {args.out}", flush=True)
    result = run(GEN_DASHSCOPE, dashscope_argv(args))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
