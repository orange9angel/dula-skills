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


def _load_directed_music(episode_dir: str, direction_path: str | None = None):
    """Return reviewed cues, an intentional empty list, or None for auto mode."""
    path = (
        os.path.abspath(direction_path)
        if direction_path
        else os.path.join(episode_dir, "config", "audio_direction.json")
    )
    if not os.path.exists(path):
        return None, None
    with open(path, "r", encoding="utf-8") as f:
        direction = json.load(f)
    mode = direction.get("policies", {}).get("musicMode", "auto")
    if mode == "auto":
        return None, path
    if direction.get("status") != "reviewed":
        raise ValueError(
            f"Audio direction must be reviewed before consuming musicMode={mode!r}: {path}"
        )
    if mode == "none":
        return [], path
    if mode != "directed":
        raise ValueError(f"Unsupported audio direction musicMode: {mode!r}")

    cues = []
    for ordinal, source in enumerate(direction.get("music", []), start=1):
        start = float(source["startTime"])
        end = float(source["endTime"])
        if start < 0 or end <= start:
            raise ValueError(f"Invalid directed music cue timing: {source!r}")
        mood = str(source.get("mood", source.get("name", ""))).strip()
        if not mood:
            raise ValueError(f"Directed music cue needs mood or name: {source!r}")
        cue = dict(source)
        cue.update(
            {
                "action": str(source.get("action", "Play")),
                "mood": mood,
                "startTime": start,
                "endTime": end,
                "fadeIn": float(source.get("fadeIn", 0.5)),
                "fadeOut": float(source.get("fadeOut", 0.5)),
                "baseVolume": float(source.get("baseVolume", source.get("volume", 0.3))),
                "name": str(source.get("name", mood)),
            }
        )
        cue.setdefault("id", f"music-{ordinal}-{mood}")
        cues.append(cue)
    return cues, path


def run(
    episode_dir: str,
    placeholder_duration: float = 30.0,
    download: bool = True,
    direction_path: str | None = None,
    ignore_direction: bool = False,
):
    episode_dir = os.path.abspath(episode_dir)
    story_path = os.path.join(episode_dir, "script.story")
    if not os.path.exists(story_path):
        print(f"[EpisodeScoring] script.story not found: {story_path}")
        return False

    music_dir = os.path.join(episode_dir, "assets", "audio", "music")
    os.makedirs(music_dir, exist_ok=True)

    with open(story_path, "r", encoding="utf-8") as f:
        story_text = f.read()

    cues = None
    direction_source = None
    if not ignore_direction:
        cues, direction_source = _load_directed_music(episode_dir, direction_path)
    if cues is None:
        director = MusicDirector()
        segments = director.analyze_story(story_text)
        cues = director.build_cue_timeline(segments)
        cue_source = "semantic-auto"
    else:
        cue_source = "audio-direction"
        print(
            f"[EpisodeScoring] Using {len(cues)} reviewed cue(s) from "
            f"{direction_source}"
        )

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
        "source": cue_source,
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
    parser.add_argument("--direction", help="Explicit audio_direction.json path")
    parser.add_argument("--ignore-direction", action="store_true", help="Ignore audio direction and regenerate semantic draft cues")
    args = parser.parse_args()

    ok = run(
        args.episode,
        placeholder_duration=args.placeholder_duration,
        download=not args.no_download,
        direction_path=args.direction,
        ignore_direction=args.ignore_direction,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
