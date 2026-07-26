#!/usr/bin/env python3
"""Create a source-hashed draft audio direction plan for a Dula episode."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from bisect import bisect_right
from pathlib import Path
from typing import Any


TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)
CHARACTER_RE = re.compile(r"\[([^\]]+)\]")
VOICE_RE = re.compile(r"\{Voice:([^}|]+)")
SCENE_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")
SFX_RE = re.compile(r"\{SFX:([^}|]+)([^}]*)\}")
MUSIC_RE = re.compile(r"\{Music:([^}|]+)([^}]*)\}")


DELIVERY_PRESETS = {
    "neutral": (0.45, 1.00, 1.00, 0.00, "normal"),
    "calm": (0.34, 0.98, 0.96, 0.00, "soft"),
    "gentle": (0.32, 0.96, 0.94, -0.10, "soft"),
    "tease": (0.56, 1.02, 0.98, 0.10, "normal"),
    "teasing": (0.56, 1.02, 0.98, 0.10, "normal"),
    "playful": (0.60, 1.03, 1.00, 0.10, "normal"),
    "playful_confident": (0.60, 1.03, 1.00, 0.00, "normal"),
    "proud": (0.58, 0.99, 1.02, -0.10, "normal"),
    "command": (0.72, 1.06, 1.05, 0.00, "strong"),
    "excited": (0.76, 1.07, 1.05, 0.20, "strong"),
    "angry": (0.78, 1.07, 1.07, 0.10, "strong"),
    "sad": (0.28, 0.94, 0.90, -0.15, "soft"),
    "worried": (0.55, 1.03, 0.96, 0.10, "normal"),
    "whisper": (0.20, 0.92, 0.82, 0.00, "soft"),
}

AMBIENCE_WORDS = (
    "roomtone",
    "room_tone",
    "ambience",
    "ambient",
    "atmos",
    "wind",
    "rain",
    "traffic",
    "crowd",
    "hum",
    "ocean",
    "forest",
)


def timestamp(groups: tuple[str, ...]) -> float:
    return (
        int(groups[0]) * 3600
        + int(groups[1]) * 60
        + int(groups[2])
        + int(groups[3]) / 1000
    )


def parse_params(tail: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in tail.lstrip("|").split("|"):
        if not item:
            continue
        if "=" not in item:
            params[item] = True
            continue
        key, value = item.split("=", 1)
        value = value.strip()
        try:
            params[key.strip()] = float(value)
        except ValueError:
            params[key.strip()] = value
    return params


def parse_story(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    entries: list[dict[str, Any]] = []
    current_scene = ""
    index = 0
    while index < len(lines):
        if not lines[index].strip().isdigit():
            index += 1
            continue
        entry_index = int(lines[index].strip())
        index += 1
        if index >= len(lines):
            break
        time_match = TIME_RE.fullmatch(lines[index].strip())
        index += 1
        if not time_match:
            continue
        start = timestamp(time_match.groups()[:4])
        end = timestamp(time_match.groups()[4:])
        content_lines = []
        while index < len(lines) and lines[index].strip():
            content_lines.append(lines[index].strip())
            index += 1
        content = " ".join(content_lines)
        scene_match = SCENE_RE.search(content)
        if scene_match:
            current_scene = scene_match.group(1)
        char_match = CHARACTER_RE.search(content)
        voice_match = VOICE_RE.search(content)
        character = char_match.group(1).strip() if char_match else None
        dialogue = re.sub(r"^@[A-Za-z_][A-Za-z0-9_]*(?:\{[^}]*\})*\s*", "", content)
        dialogue = CHARACTER_RE.sub("", dialogue)
        dialogue = re.sub(r"\{[^}]+\}", "", dialogue).strip()
        sfx = [
            {"action": match.group(1), **parse_params(match.group(2))}
            for match in SFX_RE.finditer(content)
        ]
        music = [
            {"action": match.group(1), **parse_params(match.group(2))}
            for match in MUSIC_RE.finditer(content)
        ]
        entries.append(
            {
                "index": entry_index,
                "startTime": start,
                "endTime": end,
                "content": content,
                "scene": current_scene,
                "character": character,
                "dialogue": dialogue if character and dialogue else "",
                "voiceTag": voice_match.group(1).strip() if voice_match else None,
                "sfx": sfx,
                "music": music,
            }
        )
    return entries


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_record(episode: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(episode).as_posix(),
        "sha256": sha256(path),
    }


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def locale_from_voice(voice: str) -> str:
    match = re.match(r"([a-z]{2}-[A-Z]{2})-", voice or "")
    return match.group(1) if match else "unspecified"


def delivery_for(tag: str | None) -> dict[str, Any]:
    normalized = (tag or "neutral").strip().lower().replace("-", "_")
    energy, pace, volume, pitch, emphasis = DELIVERY_PRESETS.get(
        normalized,
        DELIVERY_PRESETS["neutral"],
    )
    return {
        "tone": normalized,
        "energy": energy,
        "pace": pace,
        "volume": volume,
        "pitchSemitones": pitch,
        "emphasis": emphasis,
        "distance": "medium",
        "space": "scene",
        "pauseBeforeMs": 0,
        "pauseAfterMs": 0,
        "breath": "natural",
    }


def shot_ids_for(start: float, end: float, timeline: dict[str, Any]) -> list[str]:
    frames = timeline.get("frames", [])
    if not frames:
        return []
    times = [float(frame["at"]) for frame in frames]
    active = max(0, bisect_right(times, start) - 1)
    indices = [active]
    indices.extend(
        index
        for index, value in enumerate(times)
        if start < value < end and index != active
    )
    shots = []
    for index in indices:
        shot = str(frames[index].get("shot", "")).strip()
        if shot and shot not in shots:
            shots.append(shot)
    return shots


def cue_id(prefix: str, entry: int, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{prefix}-{entry}-{slug or 'cue'}"


def build_plan(episode: Path) -> dict[str, Any]:
    story_path = episode / "script.story"
    timeline_path = episode / "config" / "keyframe_timeline.json"
    voice_path = episode / "config" / "voice_config.json"
    mix_path = episode / "config" / "audio_mix.json"
    music_path = episode / "assets" / "audio" / "music_cues.json"
    entries = parse_story(story_path)
    timeline = load_json(timeline_path, {})
    voice_config = load_json(voice_path, {})
    mix_config = load_json(mix_path, {})
    spoken = [entry for entry in entries if entry["character"] and entry["dialogue"]]

    characters = {}
    for character in dict.fromkeys(entry["character"] for entry in spoken):
        cfg = voice_config.get(character, {})
        base = cfg.get("default", cfg) if isinstance(cfg, dict) else {}
        voice = str(base.get("voice", ""))
        characters[character] = {
            "voice": voice or "unassigned",
            "locale": locale_from_voice(voice),
            "identityPolicy": "preserve-native-voice",
        }

    dialogue = []
    for ordinal, entry in enumerate(spoken):
        dialogue.append(
            {
                "entry": entry["index"],
                "character": entry["character"],
                "text": entry["dialogue"],
                "startTime": entry["startTime"],
                "endTime": entry["endTime"],
                "scene": entry["scene"],
                "shotIds": shot_ids_for(entry["startTime"], entry["endTime"], timeline),
                "previousEntry": spoken[ordinal - 1]["index"] if ordinal else None,
                "nextEntry": spoken[ordinal + 1]["index"] if ordinal + 1 < len(spoken) else None,
                "intent": entry["voiceTag"] or "neutral",
                "subtext": "",
                "delivery": delivery_for(entry["voiceTag"]),
            }
        )

    ambience = []
    sfx = []
    for entry in entries:
        for cue in entry["sfx"]:
            name = str(cue.get("name", cue.get("type", cue.get("action", "sfx"))))
            if "offset" in cue:
                start = entry["startTime"] + float(cue["offset"])
            elif "start" in cue:
                start = float(cue["start"])
            else:
                start = entry["startTime"]
            explicit_end = cue.get("endTime", cue.get("end"))
            end = float(explicit_end) if explicit_end is not None else None
            volume = float(cue.get("baseVolume", cue.get("volume", 1.0)))
            is_bed = (
                any(word in name.lower() for word in AMBIENCE_WORDS)
                or (end is not None and end - start >= 4.0)
            )
            record = {
                "id": cue_id("ambience" if is_bed else "sfx", entry["index"], name),
                "entry": entry["index"],
                "name": name,
                "startTime": round(start, 4),
                "volume": volume,
                "role": "bed" if is_bed else "event",
                "priority": "ambience" if is_bed else "storySfx",
                "shotIds": shot_ids_for(start, min(entry["endTime"], start + 0.5), timeline),
            }
            if end is not None:
                record["endTime"] = round(end, 4)
            (ambience if is_bed else sfx).append(record)

    existing_music = load_json(music_path, {}).get("cues", [])
    music = []
    for ordinal, cue in enumerate(existing_music):
        music.append(
            {
                "id": str(cue.get("id", f"music-{ordinal + 1}-{cue.get('mood', 'cue')}")),
                **cue,
                "purpose": str(cue.get("purpose", "")),
            }
        )

    sources = [source_record(episode, story_path)]
    for path in (timeline_path, voice_path, mix_path):
        if path.exists():
            sources.append(source_record(episode, path))

    return {
        "version": 1,
        "status": "draft",
        "sources": sources,
        "policies": {
            "priority": ["dialogue", "storySfx", "ambience", "music"],
            "musicMode": "directed" if music else "auto",
            "ambienceMode": "directed" if ambience or sfx else "auto",
            "breath": "natural-tts-pauses-no-layered-breath",
        },
        "mix": {
            "dialogueVolume": float(mix_config.get("dialogueVolume", 1.0)),
            "bgmVolume": float(mix_config.get("bgmVolume", 0.3)),
            "sfxVolume": float(mix_config.get("sfxVolume", 0.8)),
            "useDucking": bool(mix_config.get("useDucking", True)),
            "duckDepth": float(mix_config.get("duckDepth", 0.3)),
        },
        "characters": characters,
        "dialogue": dialogue,
        "ambience": ambience,
        "sfx": sfx,
        "music": music,
        "exclusions": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    episode = args.episode.resolve()
    output = args.output.resolve() if args.output else episode / "config" / "audio_direction.json"
    if output.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite existing plan without --force: {output}")
    plan = build_plan(episode)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote draft audio direction to {output}: "
        f"{len(plan['dialogue'])} dialogue, {len(plan['ambience'])} ambience, "
        f"{len(plan['sfx'])} SFX, {len(plan['music'])} music cues."
    )


if __name__ == "__main__":
    main()
