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
   - Scope these passes to the work: review a new final mix as a whole; during local revisions, replay the affected lines/cues and their surrounding context instead of repeatedly reviewing every unchanged stem.
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

- **镜头窗与发声窗分开（2026-10-14 S1E4 R3）**：方向计划的 `startTime/endTime`
  必须匹配 `.story` 条目，内部留白后的实际发声窗另记 `speechWindow`。最终摆放和
  口型用同一派生发声窗；不要为通过通用验证器悄悄挪音频。重复 Foley 同时记录
  各次事件点及总起止；脚步以真实 stance 切换校验，不能复用旧版估算秒数。

- **听觉复核允许且按需使用（2026-10-14 用户澄清）**：最终目标是稳定、快速产出
  高质量动画片并迭代工艺，算法用于减少无效复核。先用 ASR/时长/电平/声画同步
  定位技术问题，再听新声线、关键情绪、重要音效和配乐进退；不能因数值通过就省掉
  必要听觉判断，也不因一处局部修订重复听遍全部素材。区分实际听过与仅数值检查。
- **导演描述必须进入实际执行链（2026-10-14 S1E4 审计）**：12 句确实用了
  seed-tts-2.0，但雷晓 6 句统一 calm，千堂葵 6 句原生情绪为空；计划里的 energy、
  intent、subtext 等没有进入生成器，混音仅执行 pace/volume 等有限参数。核查
  每项演绎决策如何落实为后端参数或表演指令；未支持的项明确标识，不能以
  reviewed、ASR 通过或供应商名称代替演绎验收。配乐和动作音效为空须作为实际
  制作取舍报告；本例前集 BGM 来自 Seed-Audio，不能误归为未接入 Suno。
- **混音放置零点必须与逐字对齐零点一致（2026-10-07 yuki_airport_t2）**：台词音频
  放进 mix 的 t0 和逐字对齐的 seg.start 若差哪怕 50ms，口型就会系统性偏。放置
  点、视素轨、字幕轨共用同一个零点常量，别各自加减"呼吸量"。
- **旁路 bus 是"额外再写一份"（同上翻车）**：给 place/mix 函数加侧 bus（如单独
  测人声电平的 voice bus）时，主 mix 必须照样写入；第一版只写侧 bus，主 mix
  丢了全部人声，靠成片峰值从 -5dBFS 掉到 -19dBFS 才暴露。
- **复用音频必须逐文件追溯（2026-10-08 bio_armor_academy_s1e2）**：标注“前集
  音效库”或片尾写某平台，不代表所有文件来自该平台。此次核查发现全片 BGM 是
  旧下载曲，16 支 SFX 中 5 支是程序合成；火山生成脚本的 skip-if-exists 保留了
  同名旧素材。核对混音实际读入路径、文件 metadata、源文件哈希及成功生成记录，
  必要时对齐解码音频确认成片来源。无证据的 provider 明确记为未核实；更新来源
  清单后再决定替换，不能把“脚本支持某平台”写成“当前成片已使用该平台”。
