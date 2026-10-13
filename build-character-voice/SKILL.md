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
   - **客观指标只能筛掉错答案，筛不出好答案**（2026-08 xiaoju_secret 教训）：F0 基频分析能锁定音高年龄段（少年男声 ≈150–170Hz），但筛不出表现力。`longshu_v3` 这类"温暖叙事/说书"音色读旁白优秀、读台词带播音腔——**先查音色的设计戏路**（陪伴/活泼/叙事/新闻），叙事腔音色不要给对话多的角色。
   - **主角音色必须盲听 A/B**：同一两句代表性台词（一句平静、一句情绪点）生成 2–3 个候选音色，让导演盲听盲选；不要让频谱数据替导演做决定。
   - 参数给足情绪跨度：gentle/bright 等状态的 rate/pitch 要拉开（如 0.93 vs 1.08），全部压在 1.0 附近会显得"端着"。

3. Compile reviewed delivery.
   - Require `audio_direction.status=reviewed`.
   - Run `scripts/compile_voice_direction.py <episode-dir>`.
   - The compiler writes engine-compatible `ttsParams` plus explicit per-line `postEffect` data.
   - Keep macro pace, pitch contour, volume, and pauses in native TTS controls. Keep SOX/ffmpeg for EQ, dynamics, distance, and very light room color.

4. Choose the synthesis path.
   - Use the normal Dula `edge` provider for stable, natural bulk dialogue.
   - CosyVoice（百炼）是 cat_leads 系列的定型主角声线；需要情感参数
     （emotion/emotion_scale）或更多角色声音时，第二通路走火山豆包
     seed-tts-2.0——接入与排坑见 [references/volcano-seedtts.md](references/volcano-seedtts.md)。
   - **说话镜头的画面侧**：对口型视频走 OmniHuman 1.5（即梦），取代贴回型口型
     cel——接入与生产纪律见 [references/volcano-omnihuman.md](references/volcano-omnihuman.md)。
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

## 正本脚本

`scripts/omnihuman_gen.py`：OmniHuman 对口型视频生成正本（六份集内拷贝字节
级一致，2026-09-27 收编自 cat_leads_e09）。接入纪律见
`references/volcano-omnihuman.md`。

## 踩坑写回（2026-10-08 9章 S1E2 R10）

- **TTS 输入必须保留标点**：剥离标点的纯字文本喂给 seed-tts 会整句连读，
  断句全丢。数据模型建议三分离：`text`（纯字，供 ASR 对齐/QC）/ `display`
  （字幕，可带标点）/ `tts_text`（TTS 输入，标点=停顿）。
- **笑声象声词 ASR 转写不稳**："哈哈"容易被转写成"呵呵"（拼音重合率 87%
  判红）或干脆不进转写。拟声笑声用单字"哈！"最稳；QC 对笑声项的转写
  失败不算内容错误，以内容字覆盖率为准。

## 2026-10-14：中文请求与时长缓存

- Windows 旧 PowerShell 的 here-string 管道到 `python -` 可能把中文变为 `?`。
  S1E4 的 Seed-Audio 因此返回 `TTSInvalidText:ReadableTextRatioTooLow`，并非服务没开通。
  中文脚本通过文件补丁写入 UTF-8 后直接执行；发送前检查请求文本没有成串 `???`，
  保留不含凭证的请求元数据。不要据一次损坏文本的响应误判服务不可用。
- 台词缓存至少校验文本、声线、情感参数和音频文件摘要，不能只看 mp3 存在。
  稍长台词先保留内在停顿，调整 `.story` 中的可用时间，再派生字幕、音频摆放和
  最终分轨口型；不截断词尾或悄悄给 QC 增大实际不存在的窗口。
- viewer 自有声音链可以从最终放置的 PCM 分轨做 10ms 能量口型，检查静默阈值及
  非说话窗内口型为零。记录这是能量开合，不是音素视素或戏感验收。
