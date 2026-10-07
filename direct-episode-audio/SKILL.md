---
name: direct-episode-audio
description: Direct and coordinate dialogue performance, ambience, Foley, story sound effects, music, silence, and final mix priorities from a script plus visual timeline. Use for complete episode sound design, cross-layer audio decisions, audio plans, or problems where voice, effects, and score compete with one another or must follow picture and dialogue together.
---

# Direct Episode Audio

Own the episode's sound intent and integration contract. Keep voice, ambience/Foley, and music as separate specialist workflows, but make them read one reviewed plan.

## Workflow

1. Read the whole episode.
   - Read `script.story`, the active visual timeline or storyboard, scene contracts, voice configuration, existing cue manifests, and current mix settings.
   - Treat `script.story` as the authoritative timing source. Treat resolved seconds in the plan as a validated cache.
   - Identify narrative beats, visible actions, speaker objectives, subtext, scene changes, reaction shots, and moments that need silence.

2. Create or refresh the shared plan.
   - Run `scripts/init_audio_direction.py <episode-dir>`.
   - Preserve a reviewed plan unless source hashes are stale or the user requested a redesign.
   - Read [references/audio-direction-contract.md](references/audio-direction-contract.md) before editing the plan.

3. Perform a contextual director pass.
   - Judge every line using the preceding line, following response, character relationship, shot size, visible action, and emotional arc.
   - Fill concise `intent` and `subtext`; tune `delivery` without changing voice identity.
   - Decide which environmental beds establish space, which visible events need Foley, which sounds should be omitted, and where music must enter, leave, duck, or stay absent.
   - Prefer meaningful negative space. Do not add a sound only because an action is visible.

4. Validate before generation.
   - Set `status` to `reviewed` only after the contextual pass.
   - Run `scripts/validate_audio_direction.py <episode-dir>`.
   - Fix stale source hashes, unmatched dialogue, unsafe voice deltas, missing shot anchors, and cue timing errors.

5. Execute specialists.
   - Use `$build-character-voice` for dialogue synthesis and per-line native/SOX treatment.
   - Use `$build-ambience-foley` for environmental beds and event sounds.
   - Use `$episode-scoring` for music cues and music assets.
   - Do not let one specialist rewrite another specialist's section.

6. Mix deterministically.
   - Keep priority `dialogue > story-critical SFX > ambience > music`.
   - Materialize final decisions into the project's established inputs: voice/tone manifests, story SFX tags or cue files, music cues, and mix config.
   - Let the engine or mixer build stems and `mixed.wav`; do not hand-edit generated audio manifests.

7. Review against picture.
   - Listen once without watching, once with picture, and once at low volume.
   - Check intelligibility, room continuity, event sync, musical exits, false sound associations, hard cuts, and excess density.
   - Rebuild raster lip sync from the final dialogue stem after voice timing changes.

## Ownership

- Own `config/audio_direction.json` and cross-layer acceptance.
- Do not own voice models, Foley synthesis algorithms, music generation, or the deterministic mixer.
- Record rejected sounds in `exclusions` so later automation does not reintroduce them.
- Keep provider-specific details out of the shared plan; specialists translate semantic intent into engine controls.

## Invalidation

- Dialogue text, voice, rate, trimming, or schedule change: regenerate dialogue, mix, and lip sync.
- Picture or action timing change: re-resolve shot/event anchors, ambience/Foley, music, and mix.
- Music-only change: regenerate music and mix; do not regenerate dialogue or lip sync.
- Ambience/Foley-only change: regenerate that stem and mix; do not regenerate dialogue or lip sync.

## 踩坑记录

- **混音放置零点必须与逐字对齐零点一致（2026-10-07 yuki_airport_t2）**：台词音频
  放进 mix 的 t0 和逐字对齐的 seg.start 若差哪怕 50ms，口型就会系统性偏。放置
  点、视素轨、字幕轨共用同一个零点常量，别各自加减"呼吸量"。
- **旁路 bus 是"额外再写一份"（同上翻车）**：给 place/mix 函数加侧 bus（如单独
  测人声电平的 voice bus）时，主 mix 必须照样写入；第一版只写侧 bus，主 mix
  丢了全部人声，靠成片峰值从 -5dBFS 掉到 -19dBFS 才暴露。
