---
name: f5-tts-voice
description: Generate personalized character voices by combining edge-tts base synthesis, ffmpeg/sox audio effects driven by personality tags, and F5-TTS zero-shot voice cloning. Use when you need custom TTS voices with distinct personality/timbre. Outputs per-line WAV files and a smart-sliced reference audio sample.
---

# F5-TTS Voice Cloning Skill

This skill adds a **personality-driven TTS pipeline** to Dula episodes:

```
edge-tts 生成基础语音
    ↓
personality tags → ffmpeg/sox 个性化效果（音高/共振峰/语速/EQ/压缩/混响/调制）
    ↓
智能切片：从最佳语音段截取 3-10s 作为 F5-TTS reference audio
    ↓
F5-TTS zero-shot 克隆音色，生成最终对白
```

It is designed as an **optional enhancement**, not a replacement for the default `dula-audio` flow.

## When to use

- You want character voices that edge-tts cannot produce directly.
- You want each character to speak with a distinct personality/timbre.
- You have no real voice recording but want to synthesize a consistent "custom voice" from a small reference clip.

## When NOT to use

- You need fast bulk generation. Keep using edge-tts or DashScope for that.
- You have a clean 3-10s real human recording. F5-TTS works best with real references, not synthesized ones.
- Your machine has no Python environment with `f5-tts` installed.

## Prerequisites

1. Python 3.10+ with `edge-tts` and `f5-tts`:
   ```bash
   pip install edge-tts f5-tts
   ```
2. `ffmpeg` in PATH (the same ffmpeg used by `dula-render`).
3. (Optional) `sox` in PATH if you prefer sox over ffmpeg filters.
4. ~2GB free space for the F5-TTS base model on first run.

## Quick Start

```bash
# From dula-story root
python dula-skills/f5-tts-voice/scripts/generate_f5_voice.py ./episodes/kimi_showcase_s1e1 --character Kimi
```

This will:
1. Read `script.story` and `config/voice_config.json`.
2. Generate base MP3s for every line spoken by `Kimi` using edge-tts.
3. Apply personality-driven audio effects based on `f5_tts.personality` tags.
4. Detect clean speech segments and extract the best 3-10s reference clip.
5. Run F5-TTS inference to produce final WAVs in `assets/audio/f5_voice/`.

## Output Layout

```
episode/
├── assets/
│   └── audio/
│       └── f5_voice/
│           ├── 005_Kimi.wav          # edge-tts + personality effects
│           ├── 005_Kimi_f5.wav       # final F5-TTS clone
│           ├── Kimi_ref.wav          # smart-sliced reference audio
│           └── Kimi_ref_text.txt     # transcript of reference clip
```

## Configuration

Extend `episode/config/voice_config.json` with an `f5_tts` block:

```json
{
  "Kimi": {
    "voice": "zh-CN-XiaoxiaoNeural",
    "rate": "+0%",
    "pitch": "+0Hz",
    "f5_tts": {
      "enabled": true,
      "personality": ["robot", "calm", "female"],
      "ref_strategy": "auto",
      "ref_duration": 5.0,
      "speed": 1.0,
      "seed": 42,
      "effect": {
        "pitch": "-2st",
        "formant": "-1"
      }
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `enabled` | If false, this character uses the normal edge-tts path. |
| `personality` | List of personality tags that drive the default effect chain. |
| `effect` | **Override** any personality-derived parameters manually. |
| `ref_strategy` | `auto` / `first` / `longest` / `<index>` — how to choose the reference line. |
| `ref_duration` | Reference clip length in seconds (3-10 recommended). |
| `speed` | F5-TTS output speed. |
| `seed` | Fixed random seed for reproducibility. |

## Personality Tags

Tags can be combined. Later tags override earlier ones.

### Gender / Age Base Layers

| Tag | Effect |
|-----|--------|
| `female` | +2st pitch, -1 formant, +4 treble, +2 presence |
| `male` | -2st pitch, +1 formant, +4 bass, -1 presence |
| `child` | +5st pitch, -3 formant, +8% speed, +5 treble |
| `elder` | -3st pitch, +2 formant, -8% speed, -2 treble, +2 warmth |

### Temperament Layers

| Tag | Effect |
|-----|--------|
| `calm` | -6% speed, soft reverb, light compression, warmth |
| `energetic` | +10% speed, bright treble, tight compression, presence |
| `brave` | -1st pitch, +1 formant, +5 bass, hall reverb, presence |
| `cold` | -1st pitch, -3 treble, long reverb, -2 presence |
| `cute` | +3st pitch, -2 formant, +6% speed, chorus |
| `funny` | +1st pitch, +12% speed, exaggerated compression, bright treble |
| `mysterious` | -2st pitch, +2 formant, dark EQ, long reverb |
| `robot` | high-pass 150Hz, +6 treble, vibrato, flanger, short reverb |
| `noble` | -1st pitch, +1 formant, +3 bass, hall reverb, presence, warmth |
| `shy` | +1st pitch, -4% speed, -3dB volume, small room |
| `worried` | +1st pitch, +6% speed, light compression, small room, anxious brightness |
| `gentle` | -1st pitch, -6% speed, soft compression, warm reverb |
| `annoyed` | +12% speed, +3 treble, -2 bass |
| `broadcast` | heavy compression, +4 presence, +3 treble, de-esser, warmth |

### Example Character Mappings

```json
{
  "Kimi": { "personality": ["robot", "calm", "female"] },
  "NewsAnchor": { "personality": ["broadcast", "calm", "female"] },
  "Hordak": { "personality": ["male", "cold", "mysterious"] },
  "Adora": { "personality": ["female", "brave", "energetic"] },
  "Nobita": { "personality": ["male", "shy", "funny"] }
}
```

## Semantic Audio Analyzer

Before any sox/ffmpeg effect is applied, the skill runs a **per-line semantic analyzer** on the dialogue text. It produces two control layers:

- **`prosody`** — fed directly into **edge-tts** (`rate`, `pitch`, `volume`).
  Handles what edge-tts does well: 语速、语调、音量.

- **`post_effect`** — fed into the **sox/ffmpeg** effect chain.
  Handles what sox/ffmpeg does well: 音色、EQ、混响、压缩、空间感.

The analyzer is rule-based and has **no external dependencies**. It understands Chinese primarily, with English fallback.

### Why split the control?

edge-tts can natively control **rate / pitch / volume** through its synthesis parameters, but it cannot change **timbre** or fine emotional color. sox/ffmpeg can reshape timbre and add space/dynamics, but pitch-shifting already-synthesized speech is lower quality than having the TTS engine generate the right pitch in the first place.

So the analyzer sends prosody to edge-tts and timbre/spatial effects to sox.

### Pipeline

```text
dialogue text
    ├─→ SemanticAudioAnalyzer
    │       ├─→ prosody (rate/pitch/volume) ──→ edge-tts
    │       └─→ post_effect (timbre/EQ/space) ──→ sox/ffmpeg
    └─→ personality preset ───────────────────────→ sox/ffmpeg
```

### What triggers changes

| Cue | edge-tts prosody | sox post_effect |
|-----|------------------|-----------------|
| `?` / `吗` / `呢` | pitch up, rate slightly down | — |
| `!` | volume up, emphasis | compression + treble |
| `...` / `……` | rate down | reverb up |
| `哈哈` / `开心` | pitch up, rate up | treble up |
| `呜` / `难过` / `哭` | pitch down, rate down | reverb + warmth |
| `生气` / `讨厌` | pitch up, rate up, volume up | compression + bass |
| `怎么办` / `担心` | pitch up, rate up | reverb + compression |
| `终于` / `放心` | pitch/rate down | warmth + reverb |
| long sentence (>20 chars) | rate slightly down | — |

Deltas are clamped to safe ranges so the character's base identity is preserved while the line still sounds emotionally appropriate.

## Reference Audio Slicing

The skill uses `ffmpeg silencedetect` to find the longest clean speech segment in the selected line, then extracts a 3-10s clip from inside that segment. This avoids:
- Leading/trailing silence
- Breath clicks
- Long pauses in the middle of the line

Selection strategies:
- `auto` (default): picks the line with the richest, cleanest speech content, **preferring the dominant language** of the character's lines. This prevents cloning Chinese dialogue with an English reference (or vice versa).
- `first`: always uses the first line.
- `longest`: uses the longest dialogue text.
- `<index>`: uses a specific entry index.

## Audio Effect Engine

The skill auto-detects `sox` in PATH and uses it **by default** when available, because sox produces stronger, broadcast-style character coloration. If sox is not installed, it falls back to ffmpeg filters.

- `--use-sox`: force sox.
- `--no-sox`: force ffmpeg even if sox is installed.

Example sox chain built for `robot` + `calm`:

```text
sinc 150-
bass 1 100
treble 6 3000
equalizer 2500 0.5q 2
pitch 0
speed 0.94
tremolo 5 22
flanger 0 2 0.08 0.16 0.54
reverb 49 38 78 40 4 -2 -5
gain -n -16
rate 24000
```

## Manual Effect Override

If personality presets are not enough, override directly in `effect`:

```json
{
  "effect": {
    "pitch": "-4st",
    "formant": "+2",
    "speed": 0.92,
    "bass": 6,
    "treble": -3,
    "reverb": 0.4,
    "compression": 0.5,
    "vibrato": 0.2,
    "highpass": 100,
    "lowpass": 7000
  }
}
```

Available manual parameters:
- `pitch`: semitones, e.g. `-2st` or `+3st`
- `formant`: semitones, e.g. `-2` or `+1`
- `speed`: playback speed factor
- `bass` / `treble`: ±dB at 100Hz / 3kHz
- `presence`: ±dB at 2.5kHz
- `warmth`: ±dB at 400Hz
- `deess`: dB of sibilance reduction around 6.5kHz
- `reverb`: 0-1 reverb amount
- `compression`: 0-1 dynamic compression amount
- `vibrato`: 0-1 vibrato depth
- `chorus`: 0-1 chorus amount
- `flanger`: 0-1 metallic flanger amount
- `highpass` / `lowpass`: cutoff frequencies in Hz

## Limitations

- **CPU inference is slow**: expect 30-90s per line without CUDA.
- **Reference quality matters**: synthesized references from edge-tts produce weaker cloning than real human recordings.
- **Long Chinese lines**: split very long lines in `script.story` to improve stability.
- **First run**: F5-TTS downloads the base model (~1.5GB) automatically.

## Future Integration

Once this skill proves useful, the next step is to integrate it as a first-class `provider` in `dula-engine/tools/generate_audio.py`, alongside `edge-tts`, `elevenlabs`, and `dashscope`.
