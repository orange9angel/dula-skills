---
name: episode-scoring
description: Direct, generate, repair, and validate episode background music from narrative arc, dialogue, picture, intentional silence, hit points, and a reviewed audio direction plan. Use when choosing music moods, motifs, cue timing, fades, ducking, musical exits, score assets, or fixing music that masks speech, fills too much space, or implies the wrong action.
---

# Episode Scoring

Score the story rather than every line. Make music support the emotional arc while leaving dialogue, story-critical effects, and intentional silence readable.

## Workflow

1. Read the complete context.
   - Read `script.story`, `config/audio_direction.json` when present, the active visual timeline, dialogue direction, ambience/SFX plan, existing music cues, and current mix config.
   - Identify scene-level arc, turns, reveals, action peaks, punchlines, and moments that should remain exposed.

2. Respect the shared direction.
   - `policies.musicMode=directed`: use the reviewed `music` cues.
   - `policies.musicMode=none`: produce an empty music cue manifest and preserve silence.
   - `policies.musicMode=auto`: run semantic scoring and treat it as a draft.
   - Do not overwrite a hand-reviewed cue plan with keyword inference.

3. Design cues.
   - Let a cue span a coherent dramatic section; do not switch mood for every sentence.
   - Enter and exit on story or picture beats.
   - Fade music before a quiet line, reveal, punchline, or story-critical sound when clarity improves.
   - Avoid tonal slides or stingers that may be mistaken for object motion, a vocalization, or a sound effect.
   - Preserve intentional music-free sections.

4. Prepare assets.
   - Prefer a curated episode asset in `assets/audio/music/` or `materials/bgm/`.
   - **正式集 BGM 首选 Seed-Audio 1.0 大模型作曲**（2026-09-05 决议，取代
     此前"首选 Pixabay 真人曲目"的策略）：prompt 工艺见
     `references/composition-prompt-craft.md`——必须写曲式分段、配器分层、
     动态对比和留白，禁止"结构平稳"类保守词和"激烈/动感"类平词。
     Pixabay 真人曲目降为对照/兜底；numpy 程序化合成只允许做占位。
     （历史注：2026-08-15 snow_fox_shrine 判死的是 numpy 合成，不是大模型
     作曲；E04-E06 已全部走 Seed-Audio。）
   - Preserve licensing metadata for external music.
   - Treat procedural loops as placeholders unless their quality is intentionally accepted.

5. Generate.
   - From the story repository root, run:

```powershell
python ../dula-skills/episode-scoring/scripts/run_scoring.py `
  ./episodes/<episode>
```

   - The runner automatically consumes `config/audio_direction.json` when present.
   - Use `--ignore-direction` only when deliberately regenerating an automatic proposal.

6. Mix and review.
   - Keep dialogue above music and duck music when sustained speech requires it.
   - Lower or remove music around story-critical SFX rather than making both louder.
   - Listen to score alone for seams, then with dialogue/SFX for masking and false associations.

## Ownership

- Own music cue intent, assets, fades, motifs, and music-layer acceptance.
- Do not alter dialogue performance, voice timing, ambience, or Foley.
- Write `assets/audio/music_cues.json`; let the engine perform deterministic mixing.

## Existing Backends

- `scripts/music_director.py`: semantic automatic scoring fallback.
- `scripts/generate_music.py`: resolve curated/downloaded music or procedural placeholders.
- `scripts/run_scoring.py`: direction-aware orchestration and cue manifest generation.
