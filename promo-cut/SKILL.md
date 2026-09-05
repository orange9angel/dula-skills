---
name: promo-cut
description: Cut a finished episode (正片 mp4) directly into a 15-30s beat-synced promo/trailer (广告片/预告片) — heuristic shot selection from keyframe_timeline.json, BGM onset-aligned hard cuts, freeze-frame grammar with push-in + white flash + synthesized shutter click, flat-color title card, straight to mp4. Use when you have a rendered episode and want a promotional short without preparing assets or using any GUI editor.
---

# Promo Cut（正片 → 广告片）

把成片直接剪成 15-30s 卡点广告片。输入一个 episode 目录，输出一支 mp4，
零 GUI 依赖（不做剪映——6.0+ 草稿已加密），只用 numpy + PIL + ffmpeg。

与 beatcut-edit 的分工：**beatcut-edit** 用备好的素材（静帧/cel 序列/manifest）
做节奏混剪，素材先行；**promo-cut** 不备素材，直接从 `output/*.mp4` 正片里
选段、切窗、踩点。要做全新编曲混剪用 beatcut-edit，要给已完成的剧集出
预告/宣传短片用 promo-cut。

## 工作流

1. **选段**：读 `config/keyframe_timeline.json`，帧条目按 shot 前缀（去掉
   末尾 `_NN` 序号）聚成镜头段，按 `file` 路径分类：`omni/` 说话镜、
   `i2v/` 动作镜、其余静态镜。启发式选窗：omni 镜头跳过开头 0.3s（气息/
   起幅）、i2v 动作段整段可用、shot 名含 `finale`/`wide` 的段落留作收尾
   （排除 `fade`）。源片取 `output/` 里 mtime 最新的 mp4。
2. **节奏**：复用 `beatcut-edit/scripts/beatcut.py` 的 `load_mono` +
   `detect_onsets` 从 BGM 检测拍点（sys.path 相对路径 import，不复制代码）。
   每 `--cut-every`（默认 2）拍一次硬切，镜头段依次取候选窗口。
3. **定格语法**：每 `--freeze-every`（默认 8）拍一次定格——抽该时刻帧冻结，
   冻结期 1.0→1.08 缓慢推近 + 开头 0.1s 闪白 + 程序合成快门声（20ms 噪声
   脉冲 + 2kHz 衰减正弦，numpy 直接叠加进音轨）。
4. **片头**：前 2.0s 字卡，晴印色板平涂（深青蓝 #2E9BD6 底 / 阳光金
   #F5B942 标题 / 云白 #FDFBF4 副标题），文字 0.3s 淡入。字体
   `C:/Windows/Fonts/msyh.ttc`，缺失时 fallback `simhei.ttf`，PIL 绘制。
5. **合成**：每个 EDL 条目用 ffmpeg `-ss/-t` 解 rawvideo 进 numpy，
   PIL 逐帧出 PNG 序列，最后 ffmpeg 编码 1920×1080 30fps H.264+AAC。
   音轨 = BGM 裁到 duration + 快门声叠加（numpy 预混成 wav，不走
   filter_complex 混音链）。

## 用法

```bash
python scripts/promo_cut.py <episode_dir> --music <bgm.wav> --out promo.mp4 \
  --duration 20 --title "猫带我去的地方" --subtitle "E06 模特小橘"
# 可调：--cut-every 2 --freeze-every 8 --freeze-dur 1.0 --title-dur 2.0 --fps 30
```

## 验收纪律

- ffprobe 查时长/分辨率/双流（h264+aac）。
- 至少抽 4 帧读图确认：片头 1s（字卡文字无乱码）、一个硬切点前后
  （画面真的换了）、一次定格中段（冻结帧无黑帧）、结尾（收在 finale）。
- 听感：快门声要落在定格起点；BGM 峰值归一化到 0.85，不削波。

## 翻车记录

- **finale 只覆盖最后一个镜头段 ≈0.4s**（E06 首跑，2026-09-05）：拍点网格最后
  一个切点离片尾往往不足 1s，只改最后一个 video 条目等于收尾没落在全景上。
  修法：最后 ~2s 内的所有 video 条目都改接到 finale 窗口。
- **快门声叠加后削波**（E06 二跑）：BGM 先归一到 0.85 再叠 0.8 幅度的快门声，
  叠加点峰值冲到 1.39（AAC 解码过冲）。修法：叠完快门声后对整条 mix 做二次
  限幅（峰值 >0.95 时整体压回 0.95）。
- **正片自带烧录字幕会带进广告片**：源 mp4 的对白字幕是烧在画面里的，选段
  无法剔除。观感上可当语境字幕用；若要不带字幕的源，得在渲染正片时关字幕。
- onset 密度高的 BGM（E06 主题曲 60s/149 onset，中位拍距 0.34s）下
  `--freeze-every 8` ≈ 每 2.7s 一次定格，密度偏大但成立；觉得闪得太勤就把
  `--freeze-every` 调到 16。
