#!/usr/bin/env python3
"""Build deterministic 12 fps Chinese anime visemes from the final dialogue stem.

The input is ``assets/audio/_temp_dialogue.wav``: the exact post-trim,
post-scheduling dialogue bus that is mixed into the rendered movie.  Using
that bus avoids the historical 200 ms discrepancy between source MP3 mouth
cues and the final mix.  Audio energy gates the mouth, while the known Chinese
dialogue selects closed/half/open limited-animation visemes per syllable.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import wave
from pathlib import Path


CUE_FPS = 60
MOUTH_FPS = 12
WINDOW_SECONDS = 0.040
ATTACK_SECONDS = 0.030
RELEASE_SECONDS = 0.080
LOOKAHEAD_FRAMES = 2
MIX_TRIM_SECONDS = 0.200

# SFX-driven mouth cues for non-dialogue sounds (e.g. animal calls). Empty by
# default; add entries shaped like
# {"index": <srt entry>, "character": <name>, "dialogue": "",
#  "sfx": <sfx stem under assets/audio/sfx/>, "timelineStart": <seconds>}.
SFX_CUES: list[dict] = []

# This episode intentionally keeps a tiny, deterministic pronunciation table
# instead of adding a runtime pinyin dependency. Every spoken Han character in
# script.story must be represented here; unknown characters fail generation.
PINYIN_BY_CHAR = {
    "些": "xie", "头": "tou",
    # E10 additions (waiting_rain dialogue)
    "云": "yun", "水": "shui", "汽": "qi", "雨": "yu", "街": "jie",
    "淋": "lin", "屋": "wu", "檐": "yan", "量": "liang", "只": "zhi",
    "剩": "sheng", "线": "xian", "洗": "xi", "边": "bian", "金": "jin",
    "日": "ri", "子": "zi", "新": "xin", "页": "ye",
    # E08 additions (drifting_page dialogue)
    "长": "zhang", "得": "de", "久": "jiu", "可": "ke", "收": "shou",
    "替": "ti", "流": "liu", "让": "rang", "记": "ji", "走": "zou",
    "追": "zhui", "送": "song", "顺": "shun",
    # E07 V5 additions
    "亮": "liang", "已": "yi", "常": "chang", "更": "geng",
    "次": "ci", "漂": "piao", "玩": "wan", "用": "yong", "经": "jing",
    # E07 V3 additions
    "净": "jing", "干": "gan", "很": "hen", "色": "se", "许": "xu",
    # E07 additions (river_willow dialogue)
    "三": "san", "伙": "huo", "十": "shi", "又": "you", "发": "fa",
    "哟": "yo", "喽": "lou", "定": "ding", "己": "ji", "年": "nian",
    "您": "nin", "柳": "liu", "树": "shu", "爷": "ye", "相": "xiang",
    "眼": "yan", "竿": "gan", "自": "zi", "花": "hua", "计": "ji",
    "认": "ren", "识": "shi", "过": "guo", "近": "jin", "错": "cuo",
    "闪": "shan", "青": "qing", "面": "mian", "鱼": "yu",
    # E06 additions (cat_model dialogue)
    "会": "hui",
    "像": "xiang",
    "再": "zai",
    "动": "dong",
    "哼": "heng",
    "嗯": "en",
    "嘛": "ma",
    "坐": "zuo",
    "开": "kai",
    "式": "shi",
    "张": "zhang",
    "待": "dai",
    "心": "xin",
    "掉": "diao",
    "最": "zui",
    "正": "zheng",
    "由": "you",
    "直": "zhi",
    "算": "suan",
    "给": "gei",
    "蝴": "hu",
    "蝶": "die",
    "跑": "pao",
    # E05 additions (morning_sketch dialogue)
    "一": "yi",
    "今": "jin",
    "们": "men",
    "友": "you",
    "在": "zai",
    "基": "ji",
    "学": "xue",
    "密": "mi",
    "晨": "chen",
    "朋": "peng",
    "清": "qing",
    "现": "xian",
    "班": "ban",
    "生": "sheng",
    "画": "hua",
    "秘": "mi",
    "见": "jian",
    "转": "zhuan",
    "那": "na",
    "陪": "pei",
    "澈": "che",
    "阿": "a",
    "作": "zuo",
    "业": "ye",
    "写": "xie",
    "完": "wan",
    "了": "le",
    "太": "tai",
    "阳": "yang",
    "还": "hai",
    "老": "lao",
    "高": "gao",
    "呢": "ne",
    "怎": "zen",
    "么": "me",
    "想": "xiang",
    "出": "chu",
    "去": "qu",
    "便": "bian",
    "利": "li",
    "店": "dian",
    "来": "lai",
    "这": "zhe",
    "里": "li",
    "做": "zuo",
    "什": "shen",
    "原": "yuan",
    "是": "shi",
    "啊": "a",
    "你": "ni",
    "每": "mei",
    "天": "tian",
    "都": "dou",
    "吗": "ma",
    "猫": "mao",
    "带": "dai",
    "我": "wo",
    "的": "de",
    "地": "di",
    "方": "fang",
    "有": "you",
    "暖": "nuan",
    "和": "huo",
    "光": "guang",
    "就": "jiu",
    "样": "yang",
    "晒": "shai",
    "着": "zhe",
    "也": "ye",
    "挺": "ting",
    "好": "hao",
    # E02 morning-riverbank lines
    "周": "zhou",
    "末": "mo",
    "早": "zao",
    "上": "shang",
    "它": "ta",
    "总": "zong",
    "比": "bi",
    "闹": "nao",
    "钟": "zhong",
    "准": "zhun",
    "时": "shi",
    "别": "bie",
    "催": "cui",
    "慢": "man",
    "点": "dian",
    "啦": "la",
    "等": "deng",
    "风": "feng",
    "舒": "shu",
    "服": "fu",
    "看": "kan",
    "个": "ge",
    # E03 dusk-homecoming lines
    "要": "yao",
    "下": "xia",
    "山": "shan",
    "知": "zhi",
    "道": "dao",
    "回": "hui",
    "桥": "qiao",
    "能": "neng",
    "远": "yuan",
    "河": "he",
    "白": "bai",
    "没": "mei",
    "注": "zhu",
    "意": "yi",
    "条": "tiao",
    "路": "lu",
    "明": "ming",
    "哪": "na",
    "呀": "ya",
    # E04 firefly-night lines (girl monologues + talking cat)
    "咦": "yi",
    "小": "xiao",
    "橘": "ju",
    "儿": "er",
    "夜": "ye",
    "安": "an",
    "静": "jing",
    "星": "xing",
    "多": "duo",
    "哇": "wa",
    "萤": "ying",
    "火": "huo",
    "虫": "chong",
    "以": "yi",
    "后": "hou",
    "吧": "ba",
    "跟": "gen",
    "紧": "jin",
    "熟": "shu",
    "快": "kuai",
    "不": "bu",
    "人": "ren",
    "说": "shuo",
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = clamp(q) * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    blend = position - low
    return ordered[low] + (ordered[high] - ordered[low]) * blend


def read_pcm16_mono(path: Path) -> tuple[int, list[float]]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frame_count = source.getnframes()
        raw = source.readframes(frame_count)

    if sample_width != 2:
        raise ValueError(f"Expected 16-bit PCM WAV, got {sample_width * 8}-bit: {path}")

    unpacked = struct.unpack(f"<{frame_count * channels}h", raw)
    scale = 1.0 / 32768.0
    if channels == 1:
        return sample_rate, [sample * scale for sample in unpacked]

    mono: list[float] = []
    for frame in range(frame_count):
        offset = frame * channels
        mono.append(sum(unpacked[offset : offset + channels]) * scale / channels)
    return sample_rate, mono


def build_envelope(samples: list[float], sample_rate: int) -> list[dict[str, float]]:
    hop_size = max(1, round(sample_rate / CUE_FPS))
    window_size = max(hop_size, round(sample_rate * WINDOW_SECONDS))
    frame_count = max(1, math.ceil(len(samples) / hop_size))
    rms_values: list[float] = []
    zcr_values: list[float] = []

    for frame in range(frame_count):
        center = frame * hop_size
        start = max(0, center - window_size // 2)
        end = min(len(samples), start + window_size)
        window = samples[start:end]
        if not window:
            rms_values.append(0.0)
            zcr_values.append(0.0)
            continue
        rms_values.append(math.sqrt(sum(sample * sample for sample in window) / len(window)))
        crossings = sum(
            1
            for left, right in zip(window, window[1:])
            if (left >= 0 > right) or (left < 0 <= right)
        )
        zcr_values.append(crossings / max(1, len(window) - 1))

    noise_floor = quantile(rms_values, 0.16)
    strong_level = max(quantile(rms_values, 0.95), noise_floor + 0.0001)
    energy_range = max(0.0001, strong_level - noise_floor)
    raw_energy = [
        math.pow(clamp((rms - noise_floor) / energy_range), 0.62)
        for rms in rms_values
    ]

    attack = 1.0 - math.exp(-(1.0 / CUE_FPS) / ATTACK_SECONDS)
    release = 1.0 - math.exp(-(1.0 / CUE_FPS) / RELEASE_SECONDS)
    envelope = 0.0
    previous_raw = 0.0
    previous_onset = 0.0
    frames: list[dict[str, float]] = []

    for index, raw_value in enumerate(raw_energy):
        target = raw_value
        for lookahead in range(1, LOOKAHEAD_FRAMES + 1):
            ahead = raw_energy[index + lookahead] if index + lookahead < len(raw_energy) else 0.0
            target = max(target, ahead * (1.0 - lookahead * 0.22))
        coefficient = attack if target > envelope else release
        envelope += (target - envelope) * coefficient
        if envelope < 0.025:
            envelope = 0.0

        raw_onset = clamp((raw_value - previous_raw) * 3.4)
        previous_onset += (raw_onset - previous_onset) * 0.42
        previous_raw = raw_value
        brightness = clamp((zcr_values[index] - 0.015) / 0.14)
        jaw_open = clamp(envelope * 0.92 + previous_onset * 0.18)
        frames.append(
            {
                "t": round(index / CUE_FPS, 4),
                "energy": round(envelope, 4),
                "jawOpen": round(jaw_open, 4),
                "onset": round(previous_onset, 4),
                "brightness": round(brightness, 4),
            }
        )

    return frames


def sample_jaw(frames: list[dict[str, float]], local_time: float) -> float:
    if not frames:
        return 0.0
    position = max(0.0, local_time) * CUE_FPS
    lower = min(len(frames) - 1, int(math.floor(position)))
    upper = min(len(frames) - 1, lower + 1)
    blend = position - math.floor(position)
    return frames[lower]["jawOpen"] + (frames[upper]["jawOpen"] - frames[lower]["jawOpen"]) * blend


def quantize_energy_cells(frames: list[dict[str, float]], duration: float) -> list[str]:
    cells: list[str] = []
    state = "closed"
    count = max(1, math.ceil(duration * MOUTH_FPS))
    for cell in range(count):
        jaw = sample_jaw(frames, (cell + 0.5) / MOUTH_FPS)
        if state == "closed":
            state = "half" if jaw >= 0.12 else "closed"
        elif state == "half":
            if jaw < 0.07:
                state = "closed"
            elif jaw >= 0.58:
                state = "open"
        else:
            if jaw < 0.07:
                state = "closed"
            elif jaw < 0.44:
                state = "half"
        cells.append(state)
    return cells


def dialogue_syllables(dialogue: str) -> list[str]:
    syllables: list[str] = []
    unknown: list[str] = []
    for char in dialogue:
        if not ("一" <= char <= "鿿"):
            continue
        pinyin = PINYIN_BY_CHAR.get(char)
        if pinyin:
            syllables.append(pinyin)
        else:
            unknown.append(char)
    if unknown:
        missing = "".join(dict.fromkeys(unknown))
        raise ValueError(f"Missing pinyin mapping for dialogue characters: {missing}")
    return syllables


def vowel_mouth_state(syllable: str) -> str:
    # A/E/O finals read as an open cel in limited anime animation; I/U/Ü
    # finals use the narrower half cel. Bilabial closures are handled below.
    if any(vowel in syllable for vowel in ("a", "o", "e")):
        return "open"
    return "half"


def syllable_mouth_state(syllable: str, phase: float, energy_state: str) -> str:
    if energy_state == "closed":
        return "closed"

    # B/P/M need a visible lip seal at the syllable onset. F uses the narrower
    # cel. Other initials transition directly into the vowel cel at 12 fps.
    if syllable.startswith(("b", "p", "m")) and phase < 0.28:
        return "closed"
    if syllable.startswith("f") and phase < 0.22:
        return "half"

    target = vowel_mouth_state(syllable)
    if target == "open" and energy_state == "half":
        return "half"
    return target


def apply_text_visemes(energy_cells: list[str], dialogue: str) -> tuple[list[str], list[str]]:
    syllables = dialogue_syllables(dialogue)
    if not syllables:
        return energy_cells[:], []

    audible = [index for index, state in enumerate(energy_cells) if state != "closed"]
    if not audible:
        return ["closed"] * len(energy_cells), syllables

    cells = ["closed"] * len(energy_cells)
    for ordinal, cell_index in enumerate(audible):
        position = ordinal * len(syllables) / len(audible)
        syllable_index = min(len(syllables) - 1, int(position))
        phase = position - syllable_index
        cells[cell_index] = syllable_mouth_state(
            syllables[syllable_index],
            phase,
            energy_cells[cell_index],
        )
    return cells, syllables


def audible_segments(cells: list[str], timeline_start: float) -> list[dict[str, float]]:
    segments: list[dict[str, float]] = []
    start_cell: int | None = None
    for index, state in enumerate(cells + ["closed"]):
        audible = state != "closed"
        if audible and start_cell is None:
            start_cell = index
        elif not audible and start_cell is not None:
            segments.append(
                {
                    "start": round(timeline_start + start_cell / MOUTH_FPS, 4),
                    "end": round(timeline_start + index / MOUTH_FPS, 4),
                }
            )
            start_cell = None
    return segments


def build(episode_dir: Path) -> dict:
    manifest_path = episode_dir / "assets" / "audio" / "manifest.json"
    dialogue_path = episode_dir / "assets" / "audio" / "_temp_dialogue.wav"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sample_rate, dialogue_samples = read_pcm16_mono(dialogue_path)

    output_entries = []
    for item in manifest.get("entries", []):
        start_time = float(item["startTime"])
        source_duration = float(item.get("audioDuration") or 0.0)
        source_offset = float(item.get("sourceOffset", MIX_TRIM_SECONDS))
        effective_duration = float(
            item.get("effectiveAudioDuration", max(0.05, source_duration - source_offset))
        )
        start_sample = max(0, round(start_time * sample_rate))
        end_sample = min(len(dialogue_samples), round((start_time + effective_duration) * sample_rate))
        frames = build_envelope(dialogue_samples[start_sample:end_sample], sample_rate)
        energy_cells = quantize_energy_cells(frames, effective_duration)
        cells, syllables = apply_text_visemes(energy_cells, item["dialogue"])
        output_entries.append(
            {
                "index": int(item["index"]),
                "character": item["character"],
                "dialogue": item["dialogue"],
                "timelineStart": round(start_time, 4),
                "timelineEnd": round(start_time + effective_duration, 4),
                "sourceDuration": round(source_duration, 6),
                "sourceOffset": source_offset,
                "effectiveDuration": round(effective_duration, 6),
                "alignment": "energy-gated-text-viseme-v1",
                "syllables": syllables,
                "audibleSegments": audible_segments(energy_cells, start_time),
                "energyCells": energy_cells,
                "cells": cells,
                "frames": frames,
            }
        )

    for cue in SFX_CUES:
        sfx_path = episode_dir / "assets" / "audio" / "sfx" / f"{cue['sfx']}.wav"
        sfx_rate, sfx_samples = read_pcm16_mono(sfx_path)
        sfx_duration = len(sfx_samples) / sfx_rate
        frames = build_envelope(sfx_samples, sfx_rate)
        energy_cells = quantize_energy_cells(frames, sfx_duration)
        start_time = float(cue["timelineStart"])
        output_entries.append(
            {
                "index": int(cue["index"]),
                "character": cue["character"],
                "dialogue": cue["dialogue"],
                "timelineStart": round(start_time, 4),
                "timelineEnd": round(start_time + sfx_duration, 4),
                "sourceDuration": round(sfx_duration, 6),
                "sourceOffset": 0.0,
                "effectiveDuration": round(sfx_duration, 6),
                "alignment": "energy-gated-sfx-v1",
                "syllables": ["miao"],
                "audibleSegments": audible_segments(energy_cells, start_time),
                "energyCells": energy_cells,
                "cells": energy_cells[:],
                "frames": frames,
            }
        )

    return {
        "version": 3,
        "timebase": "seconds",
        "signal": "post-trim-final-dialogue-stem",
        "source": "assets/audio/_temp_dialogue.wav",
        "visemeMethod": "energy-gated-text-viseme-v1",
        "visemeStates": ["closed", "half", "open"],
        "cueFrameRate": CUE_FPS,
        "mouthFrameRate": MOUTH_FPS,
        "mixTrimSeconds": MIX_TRIM_SECONDS,
        "entries": output_entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "episode_dir",
        nargs="?",
        default=Path.cwd(),
        type=Path,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    episode_dir = args.episode_dir.resolve()
    output_path = args.output or episode_dir / "config" / "lipsync_cues.json"
    payload = build(episode_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['entries'])} lipsync entries to {output_path}")
    for item in payload["entries"]:
        counts = {state: item["cells"].count(state) for state in ("closed", "half", "open")}
        print(
            f"  #{item['index']:03d} {item['character']}: "
            f"{item['effectiveDuration']:.3f}s, cells={counts}, audible={item['audibleSegments']}"
        )


if __name__ == "__main__":
    main()
