#!/usr/bin/env python3
"""
Pace checker for F5-TTS generated dialogue.

Compares each generated line's duration against a plain edge-tts baseline
(same voice, rate +0%) to answer "how much faster/slower than normal TTS?".

Usage:
  python pace_checker.py <episode-dir> [--generate-baseline]

Outputs per-line and per-character statistics:
  - actual duration
  - baseline edge-tts duration
  - ratio (actual / baseline), <1 means faster than baseline
  - characters per second (CPS)
  - suggested f5_tts.speed to match baseline
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import edge_tts


def parse_story(text):
    """Parse .story SRT-like format into dialogue entries."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    entries = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "":
            i += 1
            continue
        index_str = lines[i].strip()
        if not index_str.isdigit():
            i += 1
            continue
        index = int(index_str)
        i += 1
        if i >= len(lines):
            break
        i += 1  # skip time line
        content_lines = []
        while i < len(lines) and lines[i].strip() != "":
            content_lines.append(lines[i].strip())
            i += 1
        content = " ".join(content_lines)
        char_match = re.search(r"\[(\w+)\]", content)
        character = char_match.group(1) if char_match else None
        dialogue = re.sub(r"^@\w+(?:\{[^}]*\})*\s*", "", content)
        dialogue = re.sub(r"\[\w+\]\s*", "", dialogue)
        dialogue = re.sub(r"\{[^}]+\}\s*", "", dialogue).strip()
        if character and dialogue:
            entries.append({"index": index, "character": character, "dialogue": dialogue})
    return entries


def audio_duration(path):
    """Return audio file duration in seconds using ffprobe."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(out.stdout.strip())
    except Exception as e:
        print(f"[pace] failed to get duration for {path}: {e}", file=sys.stderr)
        return None


async def generate_baseline(text, voice, output_path):
    """Generate plain edge-tts audio with default prosody."""
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+0%", pitch="+0Hz", volume="+0%")
    await communicate.save(str(output_path))


def char_count(text):
    """Count Chinese characters (rough speech unit)."""
    return len(re.sub(r"[^\u4e00-\u9fff]", "", text))


async def main():
    parser = argparse.ArgumentParser(description="Check F5-TTS dialogue pace against edge-tts baseline")
    parser.add_argument("episode", help="Path to episode directory")
    parser.add_argument("--generate-baseline", action="store_true", help="Generate baseline edge-tts files")
    parser.add_argument("--target-cps", type=float, default=None, help="Target CPS for suggestions")
    args = parser.parse_args()

    episode = Path(args.episode).resolve()
    story_path = episode / "script.story"
    config_path = episode / "config" / "voice_config.json"
    audio_dir = episode / "assets" / "audio"
    baseline_dir = audio_dir / "_pace_baselines"

    if not story_path.exists():
        print(f"[pace] story not found: {story_path}")
        sys.exit(1)
    if not config_path.exists():
        print(f"[pace] config not found: {config_path}")
        sys.exit(1)

    story_text = story_path.read_text(encoding="utf-8")
    voice_config = json.loads(config_path.read_text(encoding="utf-8"))
    entries = parse_story(story_text)

    enabled_chars = {
        name for name, cfg in voice_config.items() if cfg.get("f5_tts", {}).get("enabled", False)
    }
    entries = [e for e in entries if e["character"] in enabled_chars]

    if args.generate_baseline:
        baseline_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    char_stats = {}
    for entry in entries:
        char = entry["character"]
        cfg = voice_config.get(char, {})
        voice = cfg.get("voice", "zh-CN-XiaoxiaoNeural")
        f5_cfg = cfg.get("f5_tts", {})
        current_speed = f5_cfg.get("speed", 1.0)

        actual_path = audio_dir / f"{entry['index']:03d}_{char}.mp3"
        baseline_path = baseline_dir / f"{entry['index']:03d}_{char}_baseline.mp3"

        actual_dur = audio_duration(actual_path) if actual_path.exists() else None

        baseline_dur = None
        if baseline_path.exists():
            baseline_dur = audio_duration(baseline_path)
        elif args.generate_baseline:
            await generate_baseline(entry["dialogue"], voice, baseline_path)
            baseline_dur = audio_duration(baseline_path)

        chars = char_count(entry["dialogue"])
        actual_cps = chars / actual_dur if actual_dur else None
        baseline_cps = chars / baseline_dur if baseline_dur else None
        ratio = actual_dur / baseline_dur if (actual_dur and baseline_dur) else None
        suggested_speed = current_speed * ratio if ratio else None

        rows.append(
            {
                "index": entry["index"],
                "character": char,
                "dialogue": entry["dialogue"],
                "chars": chars,
                "actual_dur": actual_dur,
                "baseline_dur": baseline_dur,
                "ratio": ratio,
                "actual_cps": actual_cps,
                "baseline_cps": baseline_cps,
                "current_speed": current_speed,
                "suggested_speed": suggested_speed,
            }
        )

        if char not in char_stats:
            char_stats[char] = {
                "actual_durs": [],
                "baseline_durs": [],
                "ratios": [],
                "actual_cps": [],
                "baseline_cps": [],
                "current_speed": current_speed,
            }
        if actual_dur:
            char_stats[char]["actual_durs"].append(actual_dur)
        if baseline_dur:
            char_stats[char]["baseline_durs"].append(baseline_dur)
        if ratio:
            char_stats[char]["ratios"].append(ratio)
        if actual_cps:
            char_stats[char]["actual_cps"].append(actual_cps)
        if baseline_cps:
            char_stats[char]["baseline_cps"].append(baseline_cps)

    print(f"\n{'idx':>3} {'char':>10} {'actual':>7} {'base':>7} {'ratio':>6} {'aCPS':>5} {'bCPS':>5} {'suggest':>8}  dialogue")
    print("-" * 110)
    for r in rows:
        ratio_str = f"{r['ratio']:.2f}" if r["ratio"] else "-"
        acps_str = f"{r['actual_cps']:.1f}" if r["actual_cps"] else "-"
        bcps_str = f"{r['baseline_cps']:.1f}" if r["baseline_cps"] else "-"
        suggest_str = f"{r['suggested_speed']:.2f}" if r["suggested_speed"] else "-"
        actual_str = f"{r['actual_dur']:.2f}" if r["actual_dur"] else "-"
        base_str = f"{r['baseline_dur']:.2f}" if r["baseline_dur"] else "-"
        print(
            f"{r['index']:>3} {r['character']:>10} {actual_str:>7} {base_str:>7} "
            f"{ratio_str:>6} {acps_str:>5} {bcps_str:>5} {suggest_str:>8}  {r['dialogue'][:40]}"
        )

    print("\nPer-character summary:")
    print(f"{'character':>10} {'cur_speed':>10} {'avg_ratio':>10} {'avg_aCPS':>9} {'avg_bCPS':>9} {'suggest':>9}")
    print("-" * 70)
    for char, stats in sorted(char_stats.items()):
        avg_ratio = sum(stats["ratios"]) / len(stats["ratios"]) if stats["ratios"] else None
        avg_acps = sum(stats["actual_cps"]) / len(stats["actual_cps"]) if stats["actual_cps"] else None
        avg_bcps = sum(stats["baseline_cps"]) / len(stats["baseline_cps"]) if stats["baseline_cps"] else None
        suggest = stats["current_speed"] * avg_ratio if avg_ratio else None
        print(
            f"{char:>10} {stats['current_speed']:>10.2f} "
            f"{avg_ratio:>10.2f} {avg_acps:>9.1f} {avg_bcps:>9.1f} "
            f"{suggest:>9.2f}"
        )

    if args.target_cps:
        print(f"\nTo hit target CPS {args.target_cps}:")
        print(f"{'character':>10} {'cur_speed':>10} {'suggest':>9}")
        print("-" * 40)
        for char, stats in sorted(char_stats.items()):
            if not stats["actual_cps"]:
                continue
            avg_acps = sum(stats["actual_cps"]) / len(stats["actual_cps"])
            if avg_acps <= 0:
                continue
            factor = avg_acps / args.target_cps
            suggest = stats["current_speed"] / factor
            print(f"{char:>10} {stats['current_speed']:>10.2f} {suggest:>9.2f}")


if __name__ == "__main__":
    asyncio.run(main())
