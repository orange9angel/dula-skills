#!/usr/bin/env python3
"""Generate fighting game sound effects using procedural synthesis.

No external dependencies beyond Python stdlib. Outputs 48kHz mono WAV.
Run: python generate_sfx.py <output_dir>
"""

import math
import os
import struct
import sys
import wave
import random

random.seed(42)


def _write_wav_mono(filepath, samples, sample_rate=48000):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with wave.open(filepath, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for s in samples:
            v = int(s * 32767)
            v = max(-32768, min(32767, v))
            w.writeframes(struct.pack('<h', v))


def generate_punch_hit(filepath, duration=0.18, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        thud_freq = 100 * math.exp(-t / 0.04)
        thud = math.sin(2 * math.pi * thud_freq * t) * math.exp(-t / 0.035) * 0.7
        crack = math.sin(2 * math.pi * 2500 * t) * math.exp(-t / 0.008) * 0.4
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.015) * 0.5
        rumble = math.sin(2 * math.pi * 60 * t) * math.exp(-t / 0.06) * 0.3
        sample = (thud + crack + noise + rumble) * 0.8
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_punch_light(filepath, duration=0.14, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        thud = math.sin(2 * math.pi * 120 * math.exp(-t / 0.03) * t) * math.exp(-t / 0.025) * 0.6
        crack = math.sin(2 * math.pi * 2000 * t) * math.exp(-t / 0.006) * 0.3
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.012) * 0.35
        sample = (thud + crack + noise) * 0.75
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_punch_heavy(filepath, duration=0.22, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        thud_freq = 85 * math.exp(-t / 0.05)
        thud = math.sin(2 * math.pi * thud_freq * t) * math.exp(-t / 0.04) * 0.8
        crack = math.sin(2 * math.pi * 1800 * t) * math.exp(-t / 0.01) * 0.45
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.02) * 0.5
        rumble = math.sin(2 * math.pi * 55 * t) * math.exp(-t / 0.08) * 0.35
        sample = (thud + crack + noise + rumble) * 0.82
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_kick_impact(filepath, duration=0.22, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        thud_freq = 80 * math.exp(-t / 0.05)
        thud = math.sin(2 * math.pi * thud_freq * t) * math.exp(-t / 0.045) * 0.8
        crunch = math.sin(2 * math.pi * 600 * t) * math.exp(-t / 0.012) * 0.35
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.025) * 0.4
        rumble = math.sin(2 * math.pi * 50 * t) * math.exp(-t / 0.08) * 0.35
        sample = (thud + crunch + noise + rumble) * 0.8
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_spin_kick_impact(filepath, duration=0.24, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        thud_freq = 75 * math.exp(-t / 0.055)
        thud = math.sin(2 * math.pi * thud_freq * t) * math.exp(-t / 0.05) * 0.85
        crunch = math.sin(2 * math.pi * 500 * t) * math.exp(-t / 0.015) * 0.4
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.03) * 0.45
        rumble = math.sin(2 * math.pi * 45 * t) * math.exp(-t / 0.09) * 0.4
        sample = (thud + crunch + noise + rumble) * 0.82
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_sword_slash(filepath, duration=0.3, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        freq = 3000 * math.exp(-t / 0.06)
        phase = 2 * math.pi * freq * t
        whoosh = math.sin(phase) * math.exp(-t / 0.08) * 0.5
        ring = (math.sin(2 * math.pi * 1800 * t) * 0.3 +
                math.sin(2 * math.pi * 2400 * t) * 0.2 +
                math.sin(2 * math.pi * 3200 * t) * 0.15) * math.exp(-t / 0.12) * 0.5
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.05) * 0.3
        thump = math.sin(2 * math.pi * 150 * t) * math.exp(-t / 0.02) * 0.2
        sample = (whoosh + ring + noise + thump) * 0.7
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_energy_blast(filepath, duration=0.4, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        charge_freq = 200 + 600 * min(1.0, t / 0.08)
        charge = math.sin(2 * math.pi * charge_freq * t) * 0.3
        burst_env = math.exp(-t / 0.06)
        burst = (math.sin(2 * math.pi * 800 * t) * 0.4 +
                 math.sin(2 * math.pi * 1200 * t) * 0.3) * burst_env
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.1) * 0.35
        shimmer = math.sin(2 * math.pi * 30 * t) * 0.15 * math.exp(-t / 0.15)
        sample = (charge + burst + noise + shimmer) * 0.75
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_energy_charge(filepath, duration=1.5, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        progress = t / duration
        base_freq = 150 + 400 * progress
        hum = math.sin(2 * math.pi * base_freq * t) * 0.3
        hum2 = math.sin(2 * math.pi * base_freq * 2 * t) * 0.15 * progress
        crackle = (random.random() * 2 - 1) * progress * 0.25
        rumble = math.sin(2 * math.pi * 80 * t) * progress * 0.2
        env = min(1.0, t / 0.3)
        sample = (hum + hum2 + crackle + rumble) * env * 0.6
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_dash_whoosh(filepath, duration=0.25, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        freq = 1200 * (1 - t / duration) + 300
        phase = 2 * math.pi * freq * t
        whoosh = math.sin(phase) * 0.35
        noise = (random.random() * 2 - 1)
        env = math.exp(-t / 0.08) if t > 0.02 else (t / 0.02)
        noise = noise * env * 0.5
        rumble = math.sin(2 * math.pi * 100 * t) * env * 0.2
        sample = (whoosh + noise + rumble) * 0.7
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_whoosh_fast(filepath, duration=0.18, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        freq = 2000 * (1 - t / duration) + 400
        phase = 2 * math.pi * freq * t
        whoosh = math.sin(phase) * 0.4
        noise = (random.random() * 2 - 1)
        env = math.exp(-t / 0.06) if t > 0.015 else (t / 0.015)
        noise = noise * env * 0.45
        rumble = math.sin(2 * math.pi * 120 * t) * env * 0.15
        sample = (whoosh + noise + rumble) * 0.7
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_spin_whoosh(filepath, duration=0.35, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        freq = 800 + 600 * math.sin(t / duration * math.pi)
        phase = 2 * math.pi * freq * t
        whoosh = math.sin(phase) * 0.35
        noise = (random.random() * 2 - 1)
        env = math.exp(-t / 0.1) if t > 0.03 else (t / 0.03)
        noise = noise * env * 0.5
        rumble = math.sin(2 * math.pi * 80 * t) * env * 0.25
        sample = (whoosh + noise + rumble) * 0.7
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_impact_thud(filepath, duration=0.45, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        thud_freq = 70 * math.exp(-t / 0.1)
        thud = math.sin(2 * math.pi * thud_freq * t) * math.exp(-t / 0.15) * 0.7
        crunch = (random.random() * 2 - 1) * math.exp(-t / 0.03) * 0.4
        tail = (random.random() * 2 - 1) * math.exp(-t / 0.2) * 0.15
        sub = math.sin(2 * math.pi * 40 * t) * math.exp(-t / 0.2) * 0.3
        sample = (thud + crunch + tail + sub) * 0.8
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_body_drop(filepath, duration=0.4, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        thud_freq = 65 * math.exp(-t / 0.08)
        thud = math.sin(2 * math.pi * thud_freq * t) * math.exp(-t / 0.12) * 0.75
        crunch = (random.random() * 2 - 1) * math.exp(-t / 0.04) * 0.35
        rumble = math.sin(2 * math.pi * 45 * t) * math.exp(-t / 0.15) * 0.4
        sample = (thud + crunch + rumble) * 0.8
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_block_impact(filepath, duration=0.2, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        ring = (math.sin(2 * math.pi * 2000 * t) * 0.3 +
                math.sin(2 * math.pi * 2800 * t) * 0.2) * math.exp(-t / 0.04)
        thud = math.sin(2 * math.pi * 120 * t) * math.exp(-t / 0.05) * 0.5
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.015) * 0.3
        sample = (ring + thud + noise) * 0.75
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_block_guard(filepath, duration=0.18, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        ring = (math.sin(2 * math.pi * 1600 * t) * 0.25 +
                math.sin(2 * math.pi * 2200 * t) * 0.15) * math.exp(-t / 0.035)
        thud = math.sin(2 * math.pi * 100 * t) * math.exp(-t / 0.04) * 0.45
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.012) * 0.25
        sample = (ring + thud + noise) * 0.7
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


def generate_guard_hop(filepath, duration=0.2, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = []
    for i in range(n):
        t = i / sample_rate
        whoosh_freq = 600 * math.exp(-t / 0.05)
        whoosh = math.sin(2 * math.pi * whoosh_freq * t) * math.exp(-t / 0.06) * 0.4
        noise = (random.random() * 2 - 1) * math.exp(-t / 0.04) * 0.3
        step = math.sin(2 * math.pi * 150 * t) * math.exp(-t / 0.03) * 0.35 if t < 0.08 else 0
        sample = (whoosh + noise + step) * 0.7
        samples.append(sample)
    _write_wav_mono(filepath, samples, sample_rate)
    print(f"Generated: {filepath}")


GENERATORS = {
    'punch_hit': generate_punch_hit,
    'punch_light': generate_punch_light,
    'punch_heavy': generate_punch_heavy,
    'kick_impact': generate_kick_impact,
    'spin_kick_impact': generate_spin_kick_impact,
    'sword_slash': generate_sword_slash,
    'energy_blast': generate_energy_blast,
    'energy_charge': generate_energy_charge,
    'dash_whoosh': generate_dash_whoosh,
    'whoosh_fast': generate_whoosh_fast,
    'spin_whoosh': generate_spin_whoosh,
    'impact_thud': generate_impact_thud,
    'body_drop': generate_body_drop,
    'block_impact': generate_block_impact,
    'block_guard': generate_block_guard,
    'guard_hop': generate_guard_hop,
}


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    for name, gen in GENERATORS.items():
        gen(os.path.join(output_dir, f'{name}.wav'))
    print(f"\nAll {len(GENERATORS)} SFX generated in: {output_dir}")


if __name__ == "__main__":
    main()
