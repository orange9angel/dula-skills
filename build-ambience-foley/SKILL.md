---
name: build-ambience-foley
description: Design, source, generate, place, and validate environmental ambience and story-driven Foley against dialogue and picture. Use for room tone, weather, crowds, footsteps, doors, props, impacts, sports sounds, action effects, missing or excessive SFX, false sound associations, licensing, and ambience continuity in an episode, animation, film, or motion comic.
---

# Build Ambience and Foley

Make the world audible without narrating every visible motion. Use picture, dialogue, and the reviewed sound plan to decide what deserves sound and what should remain silent.

## Workflow

1. Read the episode context.
   - **先读标准工艺链 [references/standard-ambience-pipeline.md](references/standard-ambience-pipeline.md)
     （Seed-Audio 生成纪律/底床三道验收/折尾环/摆点对位的火山-only 流水线）。**
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
   - **事件音效必须登记画面事件点位并做对位验证**（S1E3 实录）：每个事件音效在混音脚本里
     注明对应的画面事件秒点/帧；混音后用 onset 检测验证——目标点 ±0.15s 内必须存在
     onset（注意：对白/BGM 的 onset 可能比事件音更强，"窗口内最强 onset=事件"的假设
     在台词段不成立，应断言"目标点附近存在 onset"并另记最强 onset）。
     参考实现 `bio_armor_academy_s1e3/tools/check_audio_sync.py`。
   - **动画时间轴变更必须回归音效点位**：门提前、动作重排、镜头改时后，事件音效点位
     全部重核（S1E3 实录：撞门提前后 slam 对上了，但关门声早 0.3s、开门与二次关门
     无声——三轮画面验收都没覆盖音频对位）。

5. Choose sources.
   - **环境音/氛围底床默认走火山 Seed-Audio 1.0**（2026-08-30 导演决策：成本可忽略，
     不再用程序化合成做环境音）。接入见
     `../build-character-voice/references/volcano-seedtts.md` 末节；生成后必须过
     三道验收：① prompt 显式锁"平稳、无阵风、无节律性涌动、音量恒定"；
     ② 每秒 RMS 包络 max/mean < 1.4，0.5–1s 周期自相关 < 0.15；③ 4–8kHz 嘶声
     占比 < 0.2，超线做 EQ（highpass 60 + lowpass 1500）；节律不达标用 0.4s 滑动
     包络归一化兜底（E04 river_water 修复工艺）。
   - Use a clean, appropriate recorded or curated sound with compatible perspective.
   - Preserve source URL, creator, license, and any attribution requirement.
   - **一切声音走火山 Seed-Audio 生成**（2026-11-05 监制令）：算法合成
     （程序生成波形）一律禁止进正片——真实环境音与风格化战斗音效同禁
     （E04 程序化河水/夜风穿帮 + 星屑战壳 R2 程序合成音效整轮返工；
     原 fighting-sfx skill 已删除）。老素材沿用前必须跑同样的节律验收，
     "以前用过"不等于免检。

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

## 踩坑记录

- **事件音效对位不能只看 onset 检测**（crystal_aria 2026-10-31）：软起音的光爆、渐强的魔法汇聚在总线上测不到 onset，
  改读事件点 ±0.2s 内最响的 20ms 位置；放置用 `at = 事件点 − 素材起音偏移`，渐强类素材对齐其**收尾峰**。
  长尾素材（碎屑落地）里晚落的一声会撞进下一个事件（白光前 0.16s），按下一事件点截尾淡出。参考 `crystal_aria/tools/mix_song.py`。

- **Seed-Audio 素材自带前导淡入，攻击点内偏 0.18-0.44s（2026-10-28
  tomorrow_still_bright T4）**：电表滴 0.184s、接管 0.405s、开关咔哒 0.251s。
  按接触帧摆文件头=瞬头必迟到（meter×3 首轮对位 +0.19s ❌）。正法：impact 类在混音
  脚本里测素材内 RMS 首达 15% 峰值的攻击点并回退摆放；连续滑动类（抽屉滑轨/门轴/
  车轮/发条）不回退——文件头=过程起点，对齐反而把渐起段顶出窗口（drawer 二轮 ❌ 实录）。
- **底床 prompt 禁用节律暗示词（同上）**：写「呼吸般平稳」被模型做成节律性涌动
  （max/mean 1.65/corr 0.228 双 ❌）；写「走带机械声」corr 0.402 ❌。底床 prompt
  只写平稳/恒定/无周期起伏，任何比喻都会变成真实节律。


- **步态变更后的脚步缓存（2026-10-20）**：动作时长不变也可能改变触地时刻。
  从新步态的接触转换重建脚步 cue，同时记录动作脚本和步态辅助模块指纹；只校验
  剧本哈希会漏检。沿用现有鞋声时不重新生成素材，混音后比较对白/音乐/环境分轨
  哈希，确认改动只进入所需音效层，并核对实际接触轨迹。

- **稀疏底床（晨风/安静环境）循环接缝 dip（2026-10-18 stardust_clad_s1e1）**：
  篝火/嘈杂底床内容密，1s 交叉淡化接缝不会跌破连续性阈；晨风类稀疏底床
  源文件自身就有风息低谷（1s 块 RMS 掉到均值 42%），铺排叠化和半周期双层
  都治不好。正法：源内折尾做无缝环（尾部 1.5s 折进头部再平铺）+ 慢 AGC
  （增益域 0.8-2.2、1s 平滑防泵浦）抬平低谷。AGC 平滑用 uniform_filter1d，
  别用 np.convolve 全核（O(n·sr)，75s×48k 直接挂起）。

- **走拍脚步逐 stance 对位（2026-11 borrowed_moonlight R2a）**：连续踩雪 excerpt 摆进
  走拍窗会被听出"脚步不沾地"。正法：从素材 onset 分组（<0.35s 同一次踩雪）切单步片，
  按 bake planted false→true 接触时刻逐点摆放（LCG 轮换切片+增益抖动 0.8-1.0 防机枪感）。
  只有最终 cel 确实仍由 bake 同一相位驱动时，bake 的 planted 表才是接触真值。
  若重排绘画路径/步数，必须改用最终驱动器的接触表；时长没变也会失效。
  共享导出见 `walk-director/scripts/export_painted_contacts.mjs`，音频切步与摆点用
  本 skill 的 `scripts/place_contact_foley.py`，不复制旧集硬编码接触表。

- **底床尾端越界（borrowed_moonlight R3）**：`while start < cueEnd` 并不能保证素材
  不越过 cueEnd。最后一段必须裁至场景结束；机械停转要有明确声音截止点。
  `scripts/bed_loop.py` 将源尾折进头部并输出精确长度，再施加整段淡入淡出。
  平稳度检查与声音材质/距离听感分开记录。

- **画面事件核对的帧差陷阱（同上）**：全帧 diff 扫描会被镜头切换淹没（切镜帧 diff 远大
  于粒子/微光事件），事件对位要 ROI 裁剪到小区域再做差分/亮度扫描，并用 5fps 瓦片网格
  目检兜底；2D 底图管线里有些"事件"画面根本不动（如画死的门），声效是画外叙事承担，
  核对时要区分"画面事件帧"与"叙事需要点"。
