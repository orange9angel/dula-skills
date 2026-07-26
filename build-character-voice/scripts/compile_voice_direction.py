#!/usr/bin/env python3
"""Compile reviewed audio direction into Dula tone and post-effect controls."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TONE_ALIASES = {
    "calm": "neutral",
    "gentle": "gentle",
    "teasing": "tease",
    "playful": "tease",
    "playful_confident": "tease",
    "proud": "tease",
    "excited": "joyful",
    "worried": "fear",
    "whisper": "whisper",
}

EMOTION_BY_TONE = {
    "neutral": "neutral",
    "gentle": "smile",
    "tease": "smile",
    "joyful": "smile",
    "command": "anger",
    "angry": "anger",
    "surprise": "surprise",
    "fear": "fear",
    "sad": "sad",
    "whisper": "neutral",
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolved_tone(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_") or "neutral"
    return TONE_ALIASES.get(normalized, normalized)


def build_semantic_post(delivery: dict[str, Any]) -> dict[str, float | int]:
    energy = clamp(float(delivery.get("energy", 0.45)), 0.0, 1.0)
    emphasis = str(delivery.get("emphasis", "normal"))
    distance = str(delivery.get("distance", "medium"))
    space = str(delivery.get("space", "scene"))
    texture = str(delivery.get("texture", "neutral"))

    presence = {"soft": -0.4, "normal": 0.0, "strong": 0.8}.get(emphasis, 0.0)
    compression = clamp(0.03 + max(0.0, energy - 0.35) * 0.18, 0.02, 0.16)
    treble = 0.0
    warmth = 0.0
    bass = 0.0
    highpass = 80
    lowpass = 10500
    reverb = 0.0

    if texture == "warm":
        warmth += 1.0
        treble -= 0.4
    elif texture == "bright":
        treble += 0.8
    elif texture == "dark":
        treble -= 1.0
        warmth += 0.5

    if distance == "intimate":
        presence -= 0.4
        warmth += 0.4
        highpass = 70
    elif distance == "near":
        highpass = 75
    elif distance == "far":
        presence -= 1.0
        treble -= 0.8
        lowpass = 8500

    if space in {"room", "gym"}:
        reverb = 0.02 if space == "room" else 0.03
    elif space == "outdoor":
        reverb = 0.0

    return {
        "highpass": highpass,
        "lowpass": lowpass,
        "presence": round(clamp(presence, -2.0, 2.0), 2),
        "treble": round(clamp(treble, -2.0, 2.0), 2),
        "bass": round(clamp(bass, -2.0, 2.0), 2),
        "warmth": round(clamp(warmth, -2.0, 2.0), 2),
        "compression": round(compression, 3),
        "reverb": round(reverb, 3),
    }


def ffmpeg_effect(effect: dict[str, float | int]) -> dict[str, Any]:
    parts = [
        f"highpass=f={int(effect['highpass'])}",
        f"lowpass=f={int(effect['lowpass'])}",
    ]
    if effect["warmth"]:
        parts.append(f"equalizer=f=400:t=q:w=1.0:g={float(effect['warmth']):.2f}")
    if effect["presence"]:
        parts.append(f"equalizer=f=2800:t=q:w=1.1:g={float(effect['presence']):.2f}")
    if effect["treble"]:
        parts.append(f"equalizer=f=6500:t=q:w=1.2:g={float(effect['treble']):.2f}")
    if effect["bass"]:
        parts.append(f"equalizer=f=140:t=q:w=1.0:g={float(effect['bass']):.2f}")
    ratio = 1.15 + float(effect["compression"]) * 1.5
    parts.append(
        "acompressor="
        f"threshold=0.23:ratio={ratio:.2f}:attack=22:release=175:makeup=1.01"
    )
    parts.append("alimiter=limit=0.95")
    return {
        "af": ",".join(parts),
        "inheritCharacterEffect": False,
    }


def sox_effect(effect: dict[str, float | int]) -> dict[str, list[str]]:
    args = [
        "sinc",
        f"{int(effect['highpass'])}-{int(effect['lowpass'])}",
    ]
    if effect["warmth"]:
        args.extend(["equalizer", "400", "0.7q", f"{float(effect['warmth']):.2f}"])
    if effect["presence"]:
        args.extend(["equalizer", "2500", "0.7q", f"{float(effect['presence']):.2f}"])
    if effect["treble"]:
        args.extend(["treble", f"{float(effect['treble']):.2f}", "3000"])
    if effect["bass"]:
        args.extend(["bass", f"{float(effect['bass']):.2f}", "140"])
    if float(effect["compression"]) > 0.04:
        args.extend(
            [
                "compand",
                "0.02,0.15",
                "6:-80,-80,-24,-20,-12,-10",
                "-2",
                "-90",
                "0.05",
            ]
        )
    args.extend(["gain", "-n", "-1.5", "rate", "48000"])
    return {"effects": args}


def compile_entry(item: dict[str, Any]) -> dict[str, Any]:
    delivery = item.get("delivery", {})
    source_tone = str(delivery.get("tone", item.get("intent", "neutral")))
    tone = resolved_tone(source_tone)
    energy = clamp(float(delivery.get("energy", 0.45)), 0.0, 1.0)
    pace = clamp(float(delivery.get("pace", 1.0)), 0.88, 1.12)
    volume = clamp(float(delivery.get("volume", 1.0)), 0.82, 1.15)
    pitch = clamp(float(delivery.get("pitchSemitones", 0.0)), -0.75, 0.75)
    pause_after = clamp(float(delivery.get("pauseAfterMs", 0.0)), 0.0, 1200.0)
    post = build_semantic_post(delivery)
    return {
        "index": int(item["entry"]),
        "character": item["character"],
        "text": item["text"],
        "startTime": float(item["startTime"]),
        "endTime": float(item["endTime"]),
        "toneId": tone,
        "toneSource": "audio_direction",
        "confidence": 1.0,
        "ttsParams": {
            "pitch": round(pitch, 3),
            "speed": round(pace, 3),
            "volume": round(volume, 3),
            "breaks": [round(pause_after / 1000.0, 3)] if pause_after else [],
        },
        "postEffect": {
            "preserveIdentity": True,
            "semantic": post,
            "ffmpeg": ffmpeg_effect(post),
            "sox": sox_effect(post),
        },
        "emotion": EMOTION_BY_TONE.get(tone, "neutral"),
        "mouthTension": 0,
        "intensity": round(energy, 3),
        "sceneContext": item.get("scene", ""),
        "semanticExpression": EMOTION_BY_TONE.get(tone, "neutral"),
        "semanticAction": None,
        "requestedBodyGesture": {"anim": None, "intensity": 0, "layer": "none"},
        "direction": {
            "intent": item.get("intent", ""),
            "subtext": item.get("subtext", ""),
            "shotIds": item.get("shotIds", []),
            "distance": delivery.get("distance", "medium"),
            "space": delivery.get("space", "scene"),
            "breath": delivery.get("breath", "natural"),
            "pauseBeforeMs": delivery.get("pauseBeforeMs", 0),
            "pauseAfterMs": delivery.get("pauseAfterMs", 0),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    episode = args.episode.resolve()
    plan_path = args.plan.resolve() if args.plan else episode / "config" / "audio_direction.json"
    output_path = (
        args.output.resolve()
        if args.output
        else episode / "assets" / "audio" / "tone_manifest.json"
    )
    if output_path.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite without --force: {output_path}")
    plan = load_json(plan_path)
    if plan.get("status") != "reviewed" and not args.allow_draft:
        raise ValueError("audio_direction.json must be reviewed; use --allow-draft only for testing")
    entries = [compile_entry(item) for item in plan.get("dialogue", [])]
    payload = {
        "version": "1.1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": str(plan_path),
        "entryCount": len(entries),
        "entries": entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(entries)} contextual voice treatments to {output_path}")
    for entry in entries:
        tts = entry["ttsParams"]
        semantic = entry["postEffect"]["semantic"]
        print(
            f"  #{entry['index']:03d} {entry['character']} tone={entry['toneId']} "
            f"pace={tts['speed']:.3f} pitch={tts['pitch']:+.2f}st "
            f"compression={semantic['compression']:.3f} presence={semantic['presence']:+.2f}dB"
        )


if __name__ == "__main__":
    main()
