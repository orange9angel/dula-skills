#!/usr/bin/env python3
"""
Music generator for the episode-scoring skill.

Tries to fetch royalty-free music from Pixabay when a curated URL is available,
otherwise falls back to a procedural placeholder loop generated with numpy/wave.

This module has two jobs:
  1. Resolve a mood keyword to an actual .wav file on disk.
  2. Ensure that file exists, generating a placeholder if necessary.
"""

import json
import os
import sys
import wave
import math
import subprocess
from pathlib import Path

# Curated Pixabay URLs per mood. Users can override via music_registry.json.
DEFAULT_MOOD_URLS = {
    "cheerful": "https://pixabay.com/music/upbeat-cheerful-children-142776/",
    "excited": "https://pixabay.com/music/rock-fast-rock-121310/",
    "calm": "https://pixabay.com/music/ambient-calm-background-124376/",
    "sad": "https://pixabay.com/music/piano-sad-piano-140478/",
    "tense": "https://pixabay.com/music/suspense-tension-112648/",
    "angry": "https://pixabay.com/music/rock-action-energetic-rock-111546/",
    "mysterious": "https://pixabay.com/music/mysterious-mysterious-133048/",
    "romantic": "https://pixabay.com/music/romantic-romantic-piano-137333/",
    "proud": "https://pixabay.com/music/epic-epic-cinematic-121294/",
}

# Procedural generation parameters per mood
MOOD_PARAMS = {
    "cheerful": {"tempo": 130, "scale": "major", "brightness": 1.0, "energy": 0.8},
    "excited": {"tempo": 150, "scale": "major", "brightness": 1.1, "energy": 1.0},
    "calm": {"tempo": 80, "scale": "major", "brightness": 0.6, "energy": 0.3},
    "sad": {"tempo": 70, "scale": "minor", "brightness": 0.4, "energy": 0.3},
    "tense": {"tempo": 110, "scale": "minor", "brightness": 0.7, "energy": 0.9},
    "angry": {"tempo": 140, "scale": "minor", "brightness": 0.9, "energy": 1.0},
    "mysterious": {"tempo": 90, "scale": "minor", "brightness": 0.5, "energy": 0.5},
    "romantic": {"tempo": 85, "scale": "major", "brightness": 0.7, "energy": 0.4},
    "proud": {"tempo": 120, "scale": "major", "brightness": 1.0, "energy": 0.9},
}

SEMITONES = {
    "major": [0, 2, 4, 5, 7, 9, 11, 12],
    "minor": [0, 2, 3, 5, 7, 8, 10, 12],
}


def load_registry(episode_dir: str) -> dict:
    """Load music_registry.json if present, else return defaults."""
    registry_path = Path(episode_dir) / "config" / "music_registry.json"
    if registry_path.exists():
        with open(registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_MOOD_URLS, **data.get("moods", {})}
    return dict(DEFAULT_MOOD_URLS)


def ensure_music_file(
    mood: str,
    episode_dir: str,
    duration: float = 30.0,
    sample_rate: int = 48000,
    download: bool = True,
) -> str:
    """
    Ensure a music file exists for the given mood.

    Order of resolution:
      1. Existing file in episode/assets/audio/music/{mood}.wav
      2. Download from curated Pixabay URL, when downloads are enabled
      3. Procedural placeholder generation
    """
    music_dir = Path(episode_dir) / "assets" / "audio" / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    target_wav = music_dir / f"{mood}.wav"

    if target_wav.exists():
        return str(target_wav)

    if download:
        registry = load_registry(episode_dir)
        url = registry.get(mood)
        if url:
            downloaded = _try_download(url, target_wav)
            if downloaded:
                return str(target_wav)

    print(f"[MusicGenerator] Falling back to procedural placeholder for mood '{mood}'")
    generate_placeholder(str(target_wav), mood, duration=duration, sample_rate=sample_rate)
    return str(target_wav)


def _try_download(url: str, dest: Path) -> bool:
    """Try to download via the pixabay-downloader skill if available, converting to WAV."""
    skill_script = Path(__file__).parent.parent.parent / "pixabay-downloader" / "scripts" / "pixabay_download.py"
    if not skill_script.exists():
        return False

    tmp_path = dest.with_suffix(".tmp")
    try:
        result = subprocess.run(
            [sys.executable, str(skill_script), "--url", url, "--output", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size <= 1024:
            return False

        # Convert whatever was downloaded (mp3/ogg/flac) to mono 48kHz WAV
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(tmp_path), "-ac", "1", "-ar", "48000", "-acodec", "pcm_s16le", str(dest)],
            capture_output=True,
            check=True,
        )
        tmp_path.unlink(missing_ok=True)
        if dest.exists() and dest.stat().st_size > 1024:
            print(f"[MusicGenerator] Downloaded {dest.name} from Pixabay")
            return True
        return False
    except Exception as e:
        print(f"[MusicGenerator] Download attempt failed: {e}")
        return False
    finally:
        tmp_path.unlink(missing_ok=True)


def generate_placeholder(path: str, mood: str, duration: float = 30.0, sample_rate: int = 48000):
    """Generate a simple looping placeholder with numpy/wave."""
    try:
        import numpy as np
    except ImportError:
        raise RuntimeError("numpy is required for procedural placeholder generation")

    params = MOOD_PARAMS.get(mood, MOOD_PARAMS["calm"])
    tempo = params["tempo"]
    scale = params["scale"]
    brightness = params["brightness"]
    energy = params["energy"]

    base_freq = 220.0  # A3
    scale_intervals = SEMITONES[scale]

    t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
    output = np.zeros_like(t)

    # Beat period
    beat_sec = 60.0 / tempo
    beat_phase = (t / beat_sec) % 1.0

    # Simple arpeggio / pad
    num_notes = len(scale_intervals)
    for i, st in enumerate(scale_intervals[:5]):
        freq = base_freq * (2 ** (st / 12.0))
        # Slight detune for warmth
        detune = 1.0 + (i * 0.002)
        osc = np.sin(2 * np.pi * freq * detune * t)
        # Add harmonics based on brightness
        if brightness > 0.6:
            osc += 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        if brightness > 0.9:
            osc += 0.15 * np.sin(2 * np.pi * freq * 3 * t)

        # Envelope: note on every beat, longer for pad feel
        note_len = beat_sec * (1.5 if mood in ("calm", "sad", "romantic") else 1.0)
        env = np.exp(-3.0 * (beat_phase * beat_sec) / note_len)
        env = np.clip(env, 0, 1)

        # Arpeggio offset
        offset = i * 0.5 * beat_sec
        env = np.roll(env, int(offset * sample_rate))

        output += osc * env * (0.15 * energy)

    # Subtle bass pulse
    bass_freq = base_freq * 0.5
    bass = np.sin(2 * np.pi * bass_freq * t)
    bass_env = (beat_phase < 0.3).astype(float)
    output += bass * bass_env * (0.12 * energy)

    # Soft white noise shimmer for tension/energy
    if energy > 0.6:
        noise = np.random.normal(0.0, 0.05 * energy, size=t.shape)
        noise_env = np.exp(-6.0 * beat_phase)
        output += noise * noise_env

    # Soft limiter
    output = np.tanh(output * 1.5) / 1.5

    # Convert to 16-bit PCM
    output = (output * 0.7 * 32767.0).astype(np.int16)

    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(output.tobytes())

    print(f"[MusicGenerator] Wrote procedural {mood} loop -> {path} ({duration:.1f}s)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Resolve or generate music for a mood.")
    parser.add_argument("episode", help="Episode directory")
    parser.add_argument("--mood", required=True, help="Mood keyword")
    parser.add_argument("--duration", type=float, default=30.0, help="Placeholder loop duration")
    parser.add_argument("--output", help="Explicit output path")
    args = parser.parse_args()

    path = ensure_music_file(args.mood, args.episode, duration=args.duration)
    if args.output:
        import shutil
        shutil.copy(path, args.output)
        print(args.output)
    else:
        print(path)


if __name__ == "__main__":
    main()
