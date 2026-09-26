---
name: image-lipsync
description: 图像系（位图关键帧）局部 rig 工具链正本——从最终对白总线生成 12fps 三态口型时序（build_lipsync）、逐像素 diff 羽化锁回局部编辑变体（lock_region_variant / lock_mouth_variant / auto_lock_variants）、口型/眨眼 rig 与 cue 数据质检（check_lipsync）。适用于眨眼 rig、短句口型、局部微调等"框外必须逐像素一致"的 cel 工艺。
---

# Image Lip Sync（图像系局部 rig 工具链）

适用：角色画面是位图关键帧（imagegen / Seedream 出图），需要在**不重绘整帧**
的前提下做眨眼、短句口型、局部微调——工艺是"局部编辑生成变体 → 逐像素
diff → 羽化锁回底图"，保证框外像素与底图完全一致。

**别混**：程序绘制角色（Three.js 几何体）的歌唱/说话口型走
`dula-skills/song-lipsync/`，那是另一条管线（人声分离 + DTW 对齐 +
连续视素轨道），不产位图变体。

## 定位与边界（重要）

`build-continuous-story-images` 的 E04 终局决议（2026-08-30）退役的是
**"说话长镜头用贴回 cel 口型"**：对白镜头一律改走 Seedance 图+音频组合
（`--ref 图 --audio-url 台词`，模型同 pass 生成口型）或 OmniHuman 对口型
视频。**本工具链服务的部分没有退役、仍在役**：

- 眨眼 rig（eye_variants，interval 随机调度）
- 短句/少量台词的口型 rig（静帧剧集的有限动画语法）
- 非说话局部微调（表情变体、反应变体、姿态中间画）

即：codex 局部编辑 + 锁区贴回仍是**眨眼/非说话微调的首选通路**；
长对白镜头不要再用本链做 cel 口型。

## 正本纪律

本目录脚本是各 episode `tools/` 私有拷贝的**正本**（历史漂移：build_lipsync
×14、check_lipsync ×13、lock_region_variant ×9、lock_mouth_variant ×4、
auto_lock_variants ×5、build_rigs ×3，另有 relock 系若干）。收编调研结论：

| 脚本 | 正本来源 | 理由 |
|------|----------|------|
| `build_lipsync.py` | cat_leads_e10_waiting_rain（549 行） | 最新；算法与 bio_armor 版逐行相同，差异仅在 PINYIN_BY_CHAR 表——e10 是 E02–E10 累积超集 |
| `check_lipsync.py` | cat_leads_e07_river_willow（143 行） | 最新、支持 `placeholder-pre-audio-v1`；并合并了 snow_fox_shrine 版的 rig `entry` 列表支持 |
| `lock_region_variant.py` | bio_armor_academy_s1e1 | 全 9 份拷贝字节一致（bio_armor/huazhong/xiaoju/snow_fox/rainy/e01–e04） |
| `lock_mouth_variant.py` | bio_armor_academy_s1e1 | 全 4 份字节一致（bio_armor/xiaoju/rainy/basketball） |
| `auto_lock_variants.py` | cat_leads_e04_firefly_night | 全 5 份字节一致（e01–e04/snow_fox） |
| `templates/build_rigs.py` | cat_leads_e04_firefly_night | 三份中唯一带 V1.1 密度过滤修复（E04 整脸抖动教训） |
| `templates/relock_mouths_v2.py` | bio_armor_academy_s1e1 | relock 系最新；`--window` 紧贴唇区的批量重锁驱动 |
| `templates/relock_tight.py` | cat_leads_e04_firefly_night | E04 终局教训"贴回框必须收紧到特征本身"的落地实现 |

旧拷贝不删，逐集替换；**新工作一律引用本目录版本**，改进只进正本再回流。

相对原拷贝的改动仅限去剧集化（逻辑未动）：`build_lipsync.py` 的
episode_dir 默认值从"脚本上一级目录"改为 cwd；`check_lipsync.py` 的
"Cat" 音节豁免与 act cadence 时间窗改为命令行参数；`auto_lock_variants.py`
批处理模式的 episode 目录改为位置参数（默认 cwd）。

## 环境

统一用 `dula-story/.venv/Scripts/python.exe`（PIL/numpy 已装）。

## 标准工作流

```
关键帧底图（assets/keyframes/frame_XX.png）
  → ① 局部编辑生成变体（codex imagegen 首选，见 build-continuous-story-images）
  → ② diff 羽化锁回（lock_region_variant / auto_lock_variants / lock_mouth_variant）
  → ③ rig 矩形标定（templates/build_rigs.py，按集改表）
  → ④ 口型时序数据（build_lipsync.py → config/lipsync_cues.json）
  → ⑤ 质检（check_lipsync.py）
```

产物落盘约定：底图 `assets/keyframes/`、口型变体 `assets/mouth_variants/`、
眨眼变体 `assets/eye_variants/`、配置 `config/mouth_rigs.json` +
`config/eye_rigs.json` + `config/keyframe_timeline.json` +
`config/lipsync_cues.json`。

## 脚本用法（输入/输出）

### ② 锁回三件套

**`lock_region_variant.py`** — 自动 diff 锁回（首选单件工具）：

```bash
python dula-skills/image-lipsync/scripts/lock_region_variant.py \
  BASE.png VARIANT.png OUTPUT.png \
  [--margin 10] [--feather 8] [--threshold 12] \
  [--window X Y W H] [--max-area-frac 0.02]
```

输入：底图 + 局部编辑变体（必须同尺寸）。行为：diff bbox 加 margin 得贴回框，
羽化合成回底图；diff 面积超 `--max-area-frac` 判 DRIFT 拒收；变体与底图逐像素
相同判 NO DIFF 拒收；输出后自检羽化区外零泄漏（LEAK 报错）。
输出：锁回 PNG + stdout 一行 `RECT x y w h`（抄进 rig 配置）。
`--window`：生成带全图低级重编码噪点（seedream/整帧重渲染）时，把 diff 检测
限制在特征小窗内——**这就是"贴回框收紧到特征本身"的执行手段**。

**`auto_lock_variants.py`** — 批量/单件两用：

```bash
# 批量：扫描 <episode>/assets/{mouth,eye}_variants/*.png 里未锁回的变体，
# 自动配对 assets/keyframes/frame_XX.png 底图
python dula-skills/image-lipsync/scripts/auto_lock_variants.py <episode_dir>
# 单件（可手工指定贴回框）：
python dula-skills/image-lipsync/scripts/auto_lock_variants.py \
  --base B.png --variant V.png --output O.png [--rect x,y,w,h]
```

输出 `<variant_stem>_locked_v1.png`，并校验 4×feather 光晕外与底图零差异。
模块级导出 `lock_one()` 供模板驱动脚本 import。

**`lock_mouth_variant.py`** — 已知矩形的手工锁回（老工具，矩形必须外部给定）：

```bash
python dula-skills/image-lipsync/scripts/lock_mouth_variant.py \
  BASE.png VARIANT.png OUTPUT.png --rect X Y W H [--feather 8]
```

### ③ rig 标定模板（按集复制改表）

`templates/build_rigs.py`：**复制到 `<episode>/tools/` 后编辑** MOUTH_RIGS /
EYE_RIGS 两张表（rig 名 → 底图帧 + SRT 条目号），然后
`python tools/build_rigs.py`。对每张 `*_locked_v1.png` 做致密核 diff
（阈值 30 + 5×5 邻域 ≥10 变化像素，过滤整帧重渲染的稀疏噪点——E04 V1.1
整脸抖动修复），union half+open 外扩 14px，写 `config/mouth_rigs.json`
（version 2，三态 variants）与 `config/eye_rigs.json`（眨眼 interval
2.8–4.4s）。

### ④ 口型时序（build_lipsync.py）

```bash
python dula-skills/image-lipsync/scripts/build_lipsync.py <episode_dir> \
  [--output <episode_dir>/config/lipsync_cues.json]
```

输入（都在 episode_dir 下）：
- `assets/audio/manifest.json` — TTS 清单（entries: index/character/dialogue/
  startTime/audioDuration/sourceOffset/effectiveAudioDuration）
- `assets/audio/_temp_dialogue.wav` — **剪后最终对白总线**（16-bit PCM WAV）；
  用它而非源 mp3，消除历史上 200ms 的源-混音口型偏差
- `assets/audio/sfx/<name>.wav` — 仅当脚本顶部 `SFX_CUES` 非空（默认空）

行为：60fps 能量包络（RMS + ZCR，非对称 attack/release）→ 12fps 三态
closed/half/open 能量格 → 已知台词按 PINYIN_BY_CHAR 逐字选视素
（b/p/m 声头闭唇、f 半开、a/o/e 韵母开、其余半）叠加到有声格上。
**PINYIN_BY_CHAR 是正本内置的累积字表（E02–E10 台词全覆盖）；新集台词
出现表外汉字会报 `Missing pinyin mapping` 失败——把新字补进正本字表再提交，
不要在 episode 里开私表。**

输出：`config/lipsync_cues.json`（version 3；每条 entry 含 timelineStart/End、
syllables、audibleSegments、12fps cells、60fps frames，alignment 标
`energy-gated-text-viseme-v1` / `energy-gated-sfx-v1`）。

### ⑤ 质检（check_lipsync.py，只读）

```bash
python dula-skills/image-lipsync/scripts/check_lipsync.py <episode_dir> \
  [--syllable-exempt Cat] [--act-boundary 30.0]
```

输入（都在 episode_dir 下）：`config/keyframe_timeline.json`（frames: at/file/
mouthRig）、`config/mouth_rigs.json`、`config/lipsync_cues.json` +
引用的全部 PNG。
检查：时间线从 0 严格递增；rig 引用的 cue entry 存在（`entry` 支持单值或
列表）；rig 三态 variants 齐全且与底图同尺寸、rect 不出界；无未使用 rig；
cue 的 cells/energyCells 等长、状态合法、格数 ≈ effectiveDuration×mouthFrameRate；
非豁免角色的 text-viseme 条目必须有音节序列；`placeholder-pre-audio-v1`
条目打 WARN 提醒重跑 build_lipsync。
退出码 0/1；`--syllable-exempt` 用于 Cat 这类靠 SFX 发声、无音节的角色
（可重复）；`--act-boundary` 只影响 cadence 摘要打印。

### 重锁模板（救翻车现场）

- `templates/relock_mouths_v2.py`（bio_armor）：复制到 `<episode>/tools/`，
  编辑 WINDOWS（每帧紧贴唇区的小窗）与 STATES 表；先查窗内 threshold-45
  diff bbox 不触窗边（触边=嘴 diff 溢出小窗，窗要重画），再调
  `lock_region_variant.py --window` 重锁，结尾打印各 rig 的 union rect 供
  抄进 mouth_rigs.json。
- `templates/relock_tight.py`（E04）：复制到 `<episode>/tools/`，编辑
  MOUTH_BOX / EYE_BOX 表（自动致密 diff 或手工在放大裁片上量），用
  `auto_lock_variants.lock_one` 按小框重锁。依赖 `tools/` 内有可 import 的
  `auto_lock_variants.py`（复制正本或写 shim）。

## 已知坑（详见 build-continuous-story-images 教训节）

- **贴回框必须收紧到特征本身**（E04 V1.1，2026-08-30）：整脸框贴回会让
  框内重渲染噪点撑大 rig 矩形，cel 切换时整块脸抖动。用 `--window`/小 rect
  紧贴嘴/眼；自动致密 diff 对平滑人脸有效，毛发纹理和大特写要手工标定。
- **codex 局部编辑是变体唯一达标通路**：qwen-image-edit / wanx 掩码贴回
  判死（E02 V2–V4：喊叫嘴、半眯眼、贴回区色调漂移）；seedream 贴回判死
  （E04 几何漂移 2–6px，整帧重渲染改光斑 38% 像素变化）。codex 配额耗尽
  就等配额或改用 ≤0.25s crossfade 兜底，**不要 fallback 到这三家贴回**。
- **说话长镜头不要回本工艺**：退役决议见上「定位与边界」。
- 位图口型只有 closed/half/open 三态，是有限动画语法；别追求逐音素精度，
  需要精度说明这个镜头该走 Seedance 图+音频/OmniHuman。
