#!/usr/bin/env python3
"""Validate walk (motionGroup) segments in config/keyframe_timeline.json.

Checks per group: contiguity, shared continuous-pan move (static is an
error — that is the V4-era regression), >= 2 distinct cels cycling without
adjacent repeats, cel dwell within sane bounds, cel images present with
identical pixel sizes, blinkCarry continuity for eye-rigged groups, and
dula-verify sampling coverage (SRT entries sample at start + 0.9 * duration,
which structurally misses walk segments).

Usage (from dula-story root):
    python ../dula-skills/walk-director/scripts/validate_walk.py ./episodes/<episode> [--strict] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

issues = []


def error(msg):
    issues.append(("ERROR", msg))


def warning(msg):
    issues.append(("WARNING", msg))


def info(msg):
    issues.append(("INFO", msg))


def png_size(path: Path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def parse_srt_samples(story_path: Path):
    """Return sample times: entry start + 0.9 * (end - start), verify_shots.js style."""
    samples = []
    pattern = re.compile(
        r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)")
    try:
        text = story_path.read_text(encoding="utf-8")
    except OSError:
        return samples
    for m in pattern.finditer(text):
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(g) for g in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
        samples.append(start + 0.9 * (end - start))
    return samples


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path, help="episode directory")
    parser.add_argument("--timeline", type=Path, default=None,
                        help="default: <episode>/config/keyframe_timeline.json")
    parser.add_argument("--story", type=Path, default=None,
                        help="default: <episode>/script.story (for verify-coverage check)")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    ep = args.episode.resolve()
    timeline_path = args.timeline or ep / "config" / "keyframe_timeline.json"
    story_path = args.story or ep / "script.story"

    try:
        data = json.loads(timeline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load {timeline_path}: {exc}", file=sys.stderr)
        return 2
    frames = data.get("frames") or []
    duration = data.get("duration", 0)

    ats = [f.get("at") for f in frames]
    if any(b <= a for a, b in zip(ats, ats[1:])):
        error("timeline 'at' values are not strictly increasing")

    # --- collect motionGroup runs (contiguous blocks) ---
    groups = []  # {name, start_idx, end_idx}
    idx = 0
    while idx < len(frames):
        name = frames[idx].get("motionGroup")
        if not name:
            idx += 1
            continue
        end_idx = idx
        while end_idx + 1 < len(frames) and frames[end_idx + 1].get("motionGroup") == name:
            end_idx += 1
        groups.append({"name": name, "frames": frames[idx:end_idx + 1],
                       "last_index": end_idx})
        idx = end_idx + 1

    seen = {}
    for g in groups:
        if g["name"] in seen:
            error(f"motionGroup '{g['name']}' is split into non-contiguous runs")
        seen[g["name"]] = True

    for g in groups:
        name, gframes = g["name"], g["frames"]
        start_at = gframes[0]["at"]
        last_idx = g["last_index"]
        end_at = (frames[last_idx + 1]["at"] if last_idx + 1 < len(frames)
                  else duration)
        label = f"group '{name}' [{start_at}, {end_at})"

        moves = {f.get("move") for f in gframes}
        if len(moves) > 1:
            error(f"{label}: mixed moves {sorted(moves)}")
        move = gframes[0].get("move")
        if move == "static":
            error(f"{label}: move is 'static' — fixed camera reads as walking in "
                  "place; use walk_follow (continuous crop pan)")
        elif not move:
            error(f"{label}: missing move")

        files = [f.get("file") for f in gframes]
        distinct = list(dict.fromkeys(files))
        if len(distinct) < 2:
            error(f"{label}: only {len(distinct)} distinct cel, need >= 2 phases")
        for a, b in zip(files, files[1:]):
            if a == b:
                error(f"{label}: adjacent identical cel '{a}' — no visible leg swap")
        # cycling check: the file sequence should be periodic in the distinct set
        if len(distinct) >= 2:
            for i, f in enumerate(files):
                if f != distinct[i % len(distinct)]:
                    warning(f"{label}: cel order breaks the A/B cycle at beat {i} "
                            f"('{f}')")
                    break

        dwells = [round(b["at"] - a["at"], 4)
                  for a, b in zip(gframes, gframes[1:])]
        dwells.append(round(end_at - gframes[-1]["at"], 4))
        dwell = min(dwells)
        if dwell < 0.15:
            error(f"{label}: cel dwell {dwell}s < 0.15s — flickers into noise")
        elif dwell > 0.5:
            warning(f"{label}: cel dwell {dwell}s > 0.5s — reads as slideshow, "
                    "raise the rate")

        sizes = {}
        for f in distinct:
            path = ep / "assets" / f
            if not path.is_file():
                error(f"{label}: cel image missing: assets/{f}")
                continue
            size = png_size(path)
            if size is None:
                warning(f"{label}: cannot read PNG size of {f}")
                continue
            sizes[f] = size
        if len(set(sizes.values())) > 1:
            error(f"{label}: cel pixel sizes differ {sorted(set(sizes.values()))} "
                  "— framing jumps between cels")

        rigs = {f.get("eyeRig") for f in gframes}
        rigs.discard(None)
        if rigs:
            if len(rigs) > 1:
                error(f"{label}: mixed eyeRig values {sorted(rigs)}")
            for f in gframes[1:]:
                carry = f.get("blinkCarry")
                expect = round(f["at"] - start_at, 4)
                if carry is None:
                    error(f"{label}: frame at {f['at']} missing blinkCarry "
                          f"(expect {expect}) — blink clock resets per cel")
                elif abs(carry - expect) > 0.01:
                    warning(f"{label}: blinkCarry {carry} at {f['at']} != {expect}")

        info(f"{label}: {len(gframes)} beats, {len(distinct)} cels, "
             f"dwell ~{min(dwells)}s, move={move}")

    # --- dula-verify coverage blind spot ---
    if story_path.is_file():
        samples = parse_srt_samples(story_path)
        for g in groups:
            start_at = g["frames"][0]["at"]
            last_idx = g["last_index"]
            end_at = (frames[last_idx + 1]["at"] if last_idx + 1 < len(frames)
                      else duration)
            if not any(start_at <= s < end_at for s in samples):
                warning(f"group '{g['name']}' [{start_at}, {end_at}): no "
                        "dula-verify sample falls inside — accept via short "
                        "render + frame extraction (see verify-walk-shots.md)")
    else:
        info(f"script.story not found at {story_path}, skipped verify-coverage check")

    errors = [m for lvl, m in issues if lvl == "ERROR"]
    warnings = [m for lvl, m in issues if lvl == "WARNING"]

    if args.json:
        print(json.dumps({
            "groups": len(groups),
            "errors": errors,
            "warnings": warnings,
            "messages": [{"level": lvl, "message": m} for lvl, m in issues],
        }, ensure_ascii=False, indent=2))
    else:
        for lvl, msg in issues:
            print(f"{lvl}: {msg}")

    if errors or (args.strict and warnings):
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"OK: {len(groups)} walk group(s), "
          f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
