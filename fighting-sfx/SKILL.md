---
name: fighting-sfx
description: Generate fighting game sound effects (punch, kick, sword, energy, whoosh, block, body drop) using procedural synthesis. No external dependencies. Use when the user needs SFX for combat scenes, fighting games, anime action sequences, or martial arts animations. Covers punch hits (light/heavy), kick impacts, spin kick, sword slash, energy blast/charge, dash/spin/fast whooshes, block impacts, guard hop, body drop, and impact thuds. Outputs 48kHz mono WAV files.
---

# Fighting SFX Generator

Generate combat sound effects procedurally using pure Python (no external dependencies).

## Quick Start

```bash
python scripts/generate_sfx.py <output_dir>
```

Generates 16 WAV files:
- `punch_hit.wav`, `punch_light.wav`, `punch_heavy.wav`
- `kick_impact.wav`, `spin_kick_impact.wav`
- `sword_slash.wav`
- `energy_blast.wav`, `energy_charge.wav`
- `dash_whoosh.wav`, `whoosh_fast.wav`, `spin_whoosh.wav`
- `impact_thud.wav`, `body_drop.wav`
- `block_impact.wav`, `block_guard.wav`
- `guard_hop.wav`

## Technical Details

- **Sample rate**: 48kHz mono 16-bit WAV
- **Synthesis method**: Layered sine waves + noise bursts + exponential envelopes
- **No dependencies**: Uses only Python stdlib (`wave`, `struct`, `math`, `random`)
- **Duration**: 0.14s - 1.5s per sound

## Adding New Sounds

To extend `scripts/generate_sfx.py`:

1. Write a generator function following this pattern:

```python
def generate_<name>(filepath, duration=0.2, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        # Layer 1: sine wave with pitch drop
        freq = 100 * math.exp(-t / 0.04)
        tone = math.sin(2 * math.pi * freq * t) * math.exp(-t / 0.03) * 0.7
        # Layer 2: noise burst
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.015) * 0.4
        sample = (tone + noise) * 0.8
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
```

2. Register in `GENERATORS` dict
3. Add to `SKILL.md` description frontmatter

## Design Patterns

| Sound Type | Layers | Key Technique |
|---|---|---|
| Impact (punch/kick) | thud + crack + noise + rumble | Pitch-drop sine, fast decay |
| Whoosh | sweep + noise + rumble | Frequency sweep (high→low) |
| Energy | charge + burst + shimmer | Rising pitch, tremolo |
| Block | ring + thud + noise | Metallic harmonics |
| Body drop | deep thud + crunch | Very low freq (40-70Hz) |
