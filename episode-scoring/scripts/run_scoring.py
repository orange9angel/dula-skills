#!/usr/bin/env python3
"""
Episode scoring pipeline entry point.

1. Runs MusicDirector on script.story to produce music_cues.json.
2. Ensures every referenced mood has a music file (.wav) available.
3. Writes the final manifest that dula-engine/tools/generate_audio.py reads.
"""

import json
import os
import sys
from pathlib import Path

# Import sibling modules
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from music_director import MusicDirector
from generate_music import ensure_music_file


def run(episode_dir: str, placeholder_duration: float = 30.0, download: bool = True):
    episode_dir = os.path.abspath(episode_dir)
    story_path = os.path.join(episode_dir, "script.story")
    if not os.path.exists(story_path):
        print(f"[EpisodeScoring] script.story not found: {story_path}")
        return False

    music_dir = os.path.join(episode_dir, "assets", "audio", "music")
    os.makedirs(music_dir, exist_ok=True)

    with open(story_path, "r", encoding="utf-8") as f:
        story_text = f.read()

    director = MusicDirector()
    segments = director.analyze_story(story_text)
    cues = director.build_cue_timeline(segments)

    longest_cue_duration = max(
        (
            max(0.0, float(cue["endTime"]) - float(cue["startTime"]))
            for cue in cues
        ),
        default=0.0,
    )
    resolved_music_duration = max(float(placeholder_duration), longest_cue_duration)

    # Resolve music files
    for cue in cues:
        mood = cue["mood"]
        file_path = ensure_music_file(
            mood,
            episode_dir,
            duration=resolved_music_duration,
            download=download,
        )
        cue["file"] = os.path.basename(file_path)
        cue["name"] = mood

    manifest = {
        "version": 1,
        "generated": True,
        "cues": cues,
    }

    manifest_path = os.path.join(episode_dir, "assets", "audio", "music_cues.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[EpisodeScoring] Generated {len(cues)} cue(s), manifest: {manifest_path}")
    print(
        f"[EpisodeScoring] Music source mode: "
        f"{'download-or-placeholder' if download else 'placeholder-only'}, "
        f"minimum duration: {resolved_music_duration:.2f}s"
    )
    for cue in cues:
        print(f"  {cue['startTime']:>7.2f}s - {cue['endTime']:>7.2f}s  {cue['mood']:12s}  {cue['file']}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run full episode scoring pipeline.")
    parser.add_argument("episode", help="Path to episode directory")
    parser.add_argument("--placeholder-duration", type=float, default=30.0, help="Duration of generated placeholder loops")
    parser.add_argument("--no-download", action="store_true", help="Skip Pixabay downloads, always generate placeholders")
    args = parser.parse_args()

    ok = run(args.episode, placeholder_duration=args.placeholder_duration, download=not args.no_download)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
