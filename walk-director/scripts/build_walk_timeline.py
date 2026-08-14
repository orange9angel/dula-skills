#!/usr/bin/env python3
"""Expand walk segments in config/keyframe_timeline.json from config/walk_segments.json.

Each segment replaces the frames in [start, end) with evenly spaced A/B cel
beats carrying motionGroup + a continuous-pan move (default walk_follow), so
the crop camera sweeps across the whole group instead of restarting per cel.
Procedural layers (cloudDrift/dappleSway/steam/doorBand) and eyeRig are
inherited from the segment's template frame; blinkCarry is written
automatically for eye-rigged groups. Keeps the one-line-per-frame formatting.

Usage (from dula-story root):
    python ../dula-skills/walk-director/scripts/build_walk_timeline.py ./episodes/<episode> [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

INHERITED_PROPS = ("cloudDrift", "dappleSway", "steam", "doorBand")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)


def validate_segments(segments, frames, assets_dir):
    """Return list of error strings."""
    errors = []
    ranges = sorted((s["start"], s["end"], s["group"]) for s in segments)
    for (s1, e1, g1), (s2, e2, g2) in zip(ranges, ranges[1:]):
        if s2 < e1:
            errors.append(f"segments overlap: {g1} [{s1}, {e1}) vs {g2} [{s2}, {e2})")
    for seg in segments:
        group = seg.get("group", "?")
        start, end = seg["start"], seg["end"]
        if not end > start:
            errors.append(f"{group}: end ({end}) must be > start ({start})")
        cels = seg.get("cels") or []
        if len(cels) < 2:
            errors.append(f"{group}: needs >= 2 cels, got {len(cels)}")
        files = [c.get("file") for c in cels]
        if len(set(files)) != len(files):
            errors.append(f"{group}: duplicate cel file in {files}")
        for cel in cels:
            if not cel.get("file") or not cel.get("shot"):
                errors.append(f"{group}: cel missing file/shot: {cel}")
            elif not (assets_dir / cel["file"]).is_file():
                print(f"WARNING: {group}: cel image not found: assets/{cel['file']}")
        rate = seg.get("rate", 2.4)
        if not 0.5 <= rate <= 12:
            errors.append(f"{group}: rate {rate} out of sane range [0.5, 12]")
        template = next((f for f in frames if start <= f["at"] < end), None)
        if template is None:
            errors.append(
                f"{group}: no existing frame in [{start}, {end}) to inherit "
                "procedural layers from; add a base frame first")
    return errors


def beats(segment, template):
    """Expand [start, end) into evenly spaced beats cycling through cels."""
    start, end = segment["start"], segment["end"]
    rate = segment.get("rate", 2.4)
    move = segment.get("move", "walk_follow")
    cels = segment["cels"]
    n = round((end - start) * rate)
    if n < 2:
        n = 2
    step = (end - start) / n
    eye_rig = segment.get("eyeRig") or template.get("eyeRig")
    out = []
    for i in range(n):
        at = round(start + i * step, 4)
        cel = cels[i % len(cels)]
        entry = {
            "at": at,
            "file": cel["file"],
            "shot": f"{cel['shot']}_{i}",
            "move": move,
            "motionGroup": segment["group"],
        }
        for prop in INHERITED_PROPS:
            if prop in template:
                entry[prop] = template[prop]
        if eye_rig:
            entry["eyeRig"] = eye_rig
            carry = round(at - start, 4)
            if carry > 0:
                entry["blinkCarry"] = carry
        entry["transition"] = "cut"
        out.append(entry)
    return out


def rebuild(frames, segments):
    """Return new frame list with each segment range replaced by its beats."""
    pending = sorted(segments, key=lambda s: s["start"])
    templates = {}
    for seg in pending:
        templates[seg["group"]] = next(
            f for f in frames if seg["start"] <= f["at"] < seg["end"])

    def in_segment(at):
        return next(
            (s for s in pending if s["start"] <= at < s["end"]), None)

    new_frames = []
    for f in frames:
        at = f["at"]
        if in_segment(at):
            continue
        for seg in list(pending):
            if seg["end"] <= at:
                new_frames.extend(beats(seg, templates[seg["group"]]))
                pending.remove(seg)
        new_frames.append(f)
    for seg in pending:  # segment ends at/after the last frame
        new_frames.extend(beats(seg, templates[seg["group"]]))
    return new_frames


def write_timeline(path: Path, data, frames):
    lines = ["{"]
    top_keys = [k for k in data if k != "frames"]
    for key in top_keys:
        lines.append(f'  {json.dumps(key)}: {json.dumps(data[key], ensure_ascii=False)},')
    lines.append('  "frames": [')
    for i, f in enumerate(frames):
        comma = "," if i < len(frames) - 1 else ""
        lines.append("    " + json.dumps(f, ensure_ascii=False) + comma)
    lines.append("  ]")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path, help="episode directory")
    parser.add_argument("--config", type=Path, default=None,
                        help="walk segments config (default: <episode>/config/walk_segments.json)")
    parser.add_argument("--timeline", type=Path, default=None,
                        help="timeline path (default: <episode>/config/keyframe_timeline.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report frame counts without writing")
    args = parser.parse_args(argv)

    ep = args.episode.resolve()
    config_path = args.config or ep / "config" / "walk_segments.json"
    timeline_path = args.timeline or ep / "config" / "keyframe_timeline.json"

    config = load_json(config_path)
    segments = config.get("segments")
    if not segments:
        print(f"ERROR: {config_path} has no 'segments'", file=sys.stderr)
        return 2
    data = load_json(timeline_path)
    frames = data["frames"]

    errors = validate_segments(segments, frames, ep / "assets")
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 2

    new_frames = rebuild(frames, segments)
    ats = [f["at"] for f in new_frames]
    if not all(b > a for a, b in zip(ats, ats[1:])):
        print("ERROR: rebuilt timeline is not strictly increasing", file=sys.stderr)
        return 2

    groups = ", ".join(
        f"{s['group']} [{s['start']}, {s['end']}) @{s.get('rate', 2.4)} cel/s"
        for s in config["segments"])
    if args.dry_run:
        print(f"DRY-RUN: {len(frames)} -> {len(new_frames)} frames ({groups})")
        return 0

    write_timeline(timeline_path, data, new_frames)
    json.loads(timeline_path.read_text(encoding="utf-8"))  # re-parse sanity check
    print(f"OK: {len(frames)} -> {len(new_frames)} frames ({groups})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
