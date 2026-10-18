# 标准环境音/Foley 工艺链（火山-only，2026-11-05 监制令落盘）

> 环境音/音效一律火山 Seed-Audio；算法合成（程序生成波形）禁止进正片
> （原 fighting-sfx skill 与引擎 procedural_audio 链已删/废弃，历史集仅兼容）。
> 本链是 E04→星屑战壳 OP/S1E1→9章 S1E3 实战定型的流水线标准。

## 1. 角色分工

- **底床（ambience bed）**：建立连续空间；晨风/夜虫/机房嗡鸣类，低而稳。
- **Foley**：人体尺度接触声（脚步/布料/门/器物起落）。
- **事件音效（story SFX）**：叙事关键冲击/机关/变身/画外信息——每个都必须
  有画面事件锚点；没有动机的事件不加音（有生成器不是理由）。

## 2. Seed-Audio 生成纪律

- 逐支 prompt + `.source.json` 溯源（prompt/tag/sha256/provider），
  `tag=sha256(prompt)` 的 skip-if-exists 缓存——prompt 改了才重生成。
- prompt 三段式：时长+「纯音效/纯环境音，无音乐无人声」+材质与质感锁定；
  底床类额外显式锁「平稳、无阵风、无节律性涌动、音量恒定、无静默间隙」。
- 参考实现：`stardust_clad_s1e1/tools/gen_sfx.py`（JOBS 表+溯源+缓存正本）。

## 3. 底床三道验收（不过线不准进混音）

1. prompt 锁平稳（见上）；
2. 每秒 RMS 包络 max/mean < 1.4，0.5-1s 周期自相关 < 0.15；
3. 4-8kHz 嘶声占比 < 0.2（超线做 EQ：highpass 60 + lowpass 1500）。
节律不达标用 0.4s 滑动包络归一化兜底（E04 river_water 修复工艺）。
老素材沿用前必须跑同样的验收，"以前用过"不等于免检。

## 4. 铺底工艺

- **源内折尾无缝环**：尾部 1.5s 折进头部再平铺——稀疏底床（晨风类）的
  铺排叠化接缝必 dip（S1E1 翻车实录），折尾比叠化干净。
- **慢 AGC 抬平低谷**：增益域 0.8-2.2、1s 平滑（uniform_filter1d，
  别用 np.convolve 全核——75s×48k 会挂起）。
- 跨场景换床用交叉淡化；底床在对白 duck 总线里与 BGM 同层受压。
- 参考实现：`stardust_clad_s1e1/tools/build_audio.py` 的 `build_bed()`。

## 5. Foley/事件摆点纪律

- 摆点时刻=画面事件帧（performance/谱面 T 表是唯一时刻源）；瞬态对接触帧，
  不对动作起点；动画时间轴变更后全部点位重核（S1E3 撞门提前翻车实录）。
- 混音后 onset 对位验证：目标点 ±0.15s 内必须存在 onset；断言"附近存在 onset"
  而非"窗口内最强 onset=事件"（台词/BGM 的 onset 可能更强）。
  参考实现：`stardust_clad_s1e1/tools/check_audio_sync.py`、
  `bio_armor_academy_s1e3/tools/check_audio_sync.py`。

## 6. 与对白/配乐总线关系

- 优先级：对白 > 叙事关键 SFX > 环境底床 > 音乐；对白 duck −6~-8dB/150ms 平滑窗，
  底床与 BGM 同被 duck。
- 混音峰值上限 −2.2dBFS（AAC 过冲留量）；出片后 AAC 解码复验峰值 ≤0.8。
- 连续性检查要单轨验底床（别量混音——歌曲尾奏回落会误判 dropout）。
