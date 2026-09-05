---
name: build-ambience-foley
description: Design, source, generate, place, and validate environmental ambience and story-driven Foley against dialogue and picture. Use for room tone, weather, crowds, footsteps, doors, props, impacts, sports sounds, action effects, missing or excessive SFX, false sound associations, licensing, and ambience continuity in an episode, animation, film, or motion comic.
---

# Build Ambience and Foley

Make the world audible without narrating every visible motion. Use picture, dialogue, and the reviewed sound plan to decide what deserves sound and what should remain silent.

## Workflow

1. Read the episode context.
   - Read `script.story`, `config/audio_direction.json`, the active picture timeline, scene contract, existing SFX assets/tags, music cues, and exclusions.
   - Read [references/selection-and-mix.md](references/selection-and-mix.md) before adding sounds.
   - Preserve rejected sounds recorded in `exclusions`.

2. Separate sound roles.
   - Use ambience beds to establish continuous space.
   - Use Foley for human-scale contact: steps, cloth, doors, ball bounces, handling, and landings.
   - Use story effects for narratively important impacts, mechanisms, transformations, or offscreen information.
   - Keep vocal breaths, sighs, sobs, and exertion inside the character-voice workflow unless they are explicitly nonverbal performance cues.

3. Select only motivated events.
   - Prioritize sounds that clarify contact, weight, location, consequence, or an offscreen cause.
   - Skip generic whooshes for ordinary thrown objects or camera motion unless the style is deliberately exaggerated.
   - Do not add a sound merely because a generator exists.
   - Leave room around dialogue, punchlines, reveals, and visually self-explanatory motion.

4. Anchor to picture and story.
   - Reference stable entry, shot, or event IDs; resolve seconds from the current story/picture.
   - Align impact transients to visible contact, not motion onset.
   - Start ambience before or at scene entry and crossfade beds across location changes.
   - Materialize Dula decisions as explicit `{SFX:...}` tags or the engine's established cue inputs so `script.story` remains the timing authority.

5. Choose sources.
   - **环境音/氛围底床默认走火山 Seed-Audio 1.0**（2026-08-30 导演决策：成本可忽略，
     不再用程序化合成做环境音）。接入见
     `../build-character-voice/references/volcano-seedtts.md` 末节；生成后必须过
     三道验收：① prompt 显式锁"平稳、无阵风、无节律性涌动、音量恒定"；
     ② 每秒 RMS 包络 max/mean < 1.4，0.5–1s 周期自相关 < 0.15；③ 4–8kHz 嘶声
     占比 < 0.2，超线做 EQ（highpass 60 + lowpass 1500）；节律不达标用 0.4s 滑动
     包络归一化兜底（E04 river_water 修复工艺）。
   - Prefer a clean, appropriate recorded or curated sound with compatible perspective.
   - Preserve source URL, creator, license, and any attribution requirement.
   - Procedural synthesis 仅限非真实/风格化声音（魔法、机械、UI 音等），
     **真实环境音禁止程序化**（E04 教训：程序化河水的 0.5s 汩声节律穿帮，
     程序化夜风被观众判"不自然"）。老素材沿用前必须跑同样的节律验收，
     "以前用过"不等于免检。
   - Use the sibling `fighting-sfx` workflow only for deliberately stylized combat effects.

6. Build and mix the layer.
   - Keep beds low and stable; avoid audible looping.
   - Match distance, room, and material across consecutive shots.
   - Give story-critical effects transient space without masking speech.
   - Avoid embedding music-like tonal glides in Foley when they may be mistaken for a narrative sound.

7. Review against picture.
   - Solo ambience, solo Foley/SFX, then listen with dialogue and music.
   - Check sync, perspective, repetition, abrupt bed changes, excessive density, and sounds that imply the wrong object or action.
   - Remove any sound whose absence improves clarity or naturalness.

## Ownership

- Own environmental beds, Foley/event assets, cue placement, source records, and this layer's review.
- Do not alter dialogue performance, voice timing, or music composition.
- Do not compensate for a weak visual edit by filling every gap with sound.
- Respect the director plan's priority: dialogue, then story-critical SFX, then ambience, then music.
