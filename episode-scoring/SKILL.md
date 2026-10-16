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
   - 用户或工作区明确指定平台时优先遵守，例如 Suno 配乐、火山环境音/配音。
     下列历史默认后端不覆盖当前指示。记录每个 cue 的实际 provider 与素材摘要；
     平台失败时明确待办，不让通用音效脚本把配乐静默重生成到另一平台。
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

## 踩坑记录

- **火山 Seed-Audio 器乐 BGM 链路可用（2026-10-07 yuki_airport_t2）**：
  `volc-voice-casting/scripts/seedaudio_gen.py`（`.env.speech` 的 SPEECH key）
  一次生成 112s 纯器乐成功，适合 vlog 铺底；长度不足时 1.5s 交叉淡化接环。
- **器乐"无歌声验证"的幻觉串**：faster-whisper 转写纯音乐会产出「字幕by索兰娅」
  式固定幻觉串——这是无语音内容的假阳性，不能据此误判有歌词。
- **铺底电平口径（本集实测）**：BGM 基准 RMS = 人声 RMS −12dB；对白段按口型
  gate 包络 duck 再 −7dB（150ms 平滑）；旁白/彩蛋段整体 ×0.7；成片峰值留
  ≥1dB 余量（本集 -4.96 dBFS）。

（S1E2 补充，2026-10-07 bio_armor_academy_s1e2）
- **双 BGM 叠加不能当作切换（2026-10-08 核查修正）**：S1E2 曾让旧主题曲全程
  铺底，再在 26.621–51.154s 叠加独立打斗曲；两首曲子同时发声可能造成节奏与
  和声冲突。默认用退出/进入或短交叉淡化完成换曲，持续叠加须有明确配器设计并
  验收。侧 bus 的 skip_mix 仅防止同一素材重复入主混音，不能防止两首不同曲子
  互相干扰。旧 BGM 文件名及片尾署名不足以证明生成平台，必须查实际素材来源。
- **既有音效库事件总线复用**：前集 SFX 拷贝到本集 assets（NOTES 注明来源），
  按条目内相对时间放置（落地 55%、命中 65%/72% 等），环境床低 dB 循环垫全程。
