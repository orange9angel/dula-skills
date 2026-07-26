---
name: build-character-voice
description: Direct, generate, repair, and validate contextual character dialogue using native TTS prosody, restrained per-line SOX or ffmpeg treatment, optional F5 voice cloning, and final-stem timing. Use for casting voices, Taiwanese or other locale-appropriate speech, fixing voices that sound too old, too high, artificial, rushed, emotionally flat, or inconsistent with surrounding dialogue and picture.
---

# Build Character Voice

Create acting first and audio processing second. Preserve a believable native voice identity while translating the reviewed episode direction into per-line delivery.

## Workflow

1. Read context before choosing parameters.
   - Read `script.story`, `config/audio_direction.json`, `config/voice_config.json`, the visual timeline, and existing tone/audio manifests.
   - For each line, consider the previous line, expected response, relationship, subtext, visible action, shot distance, and scene-level emotional arc.
   - Read [references/contextual-delivery.md](references/contextual-delivery.md) before changing pitch, formants, speed, breath, or SOX effects.

2. Cast the native voice.
   - Prefer a provider voice already matching locale, age impression, and character energy.
   - For Taiwanese Mandarin, audition native `zh-TW` voices before any pitch or formant processing.
   - Compare complete lines at normal volume. Do not cast from isolated syllables.
   - Keep character identity controls in `voice_config.json`; keep per-line acting in `audio_direction.json`.

3. Compile reviewed delivery.
   - Require `audio_direction.status=reviewed`.
   - Run `scripts/compile_voice_direction.py <episode-dir>`.
   - The compiler writes engine-compatible `ttsParams` plus explicit per-line `postEffect` data.
   - Keep macro pace, pitch contour, volume, and pauses in native TTS controls. Keep SOX/ffmpeg for EQ, dynamics, distance, and very light room color.

4. Choose the synthesis path.
   - Use the normal Dula `edge` provider for stable, natural bulk dialogue.
   - Use the sibling `f5-tts-voice` workflow only when a genuinely custom timbre is required and a clean reference exists.
   - Do not enable F5 merely to change age or gender. Select a better native voice.
   - Regenerate only affected characters or lines when the backend supports it.

5. Generate and inspect dry dialogue first.
   - Listen without music or SFX.
   - Check age impression, locale, pace, intention, pauses, consonant clarity, line endings, and continuity across adjacent lines.
   - Reject processing that is noticeable as an effect.

6. Finalize timing.
   - Build the final post-trim dialogue stem and manifest.
   - Keep breathing inside the performed line or natural pause structure. Do not layer generic breath samples unless the action explicitly calls for an audible inhale.
   - Rebuild raster lip sync from this final dialogue stem after any timing change.

## Processing Boundary

- Use native TTS for `rate`, modest pitch contour, volume, pauses, pronunciation, and emphasis.
- Use SOX/ffmpeg for high/low-pass cleanup, small EQ moves, light compression, distance filtering, and restrained space.
- Do not use post pitch/formant shifts to manufacture youth, femininity, masculinity, or accent.
- Do not stack text-keyword inference, director controls, character presets, and post effects without checking the combined result.
- Give reviewed director controls precedence over single-line keyword inference.

## Dula Integration

- Write compiled controls to `assets/audio/tone_manifest.json`, which the normal audio generator consumes.
- Preserve text and character matching so stale manifests are rejected.
- The default engine consumes `postEffect.ffmpeg`; the F5/SOX backend consumes `postEffect.semantic`.
- Keep generated clips and `mixed.wav` out of source control according to the episode repository rules.
