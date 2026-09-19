---
name: suno-driver
description: Suno 网页版自动化（Playwright 持久会话）—— 无公开 API 时的 Suno 生成/下载驱动。需要自动化 Suno 抽卡、批量生成歌曲时使用。灰色地带：仅限自己的付费账号低频自用。
---

# Suno Driver（网页自动化）

Suno **没有公开自助 API**（官方 API 仅企业定制 $499/月起）。本 skill 用
Playwright 持久化会话驱动网页版，完成 生成→下载 自动化。

## 风险与纪律（必读）

- **灰色地带**：自动化网页版违反 Suno ToS 的字面条款。仅限自己的付费账号、
  低频（每天几十首以内）、人类化节奏使用。账号有被限制的风险。
- 会话档案 `.suno_profile/` 含登录态，**必须 gitignore**，绝不提交。
- 页面改版会导致选择器失效：先跑 `--probe` 拿页面结构，校准脚本顶部
  的选择器表，再跑生成。

## 用法

```bash
cd dula-story
# 1. 首次：headed 登录（手动登录后回车关闭，会话存 .suno_profile）
.venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_generate.py --login
# 2. 页面结构变了就跑探测，把 suno_probe.json 交给代理校准选择器
.venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_generate.py --probe --out tmp/
# 3. 生成（人声版 / 器乐版）
.venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_generate.py \
  --style "Chinese cinematic ballad, xun, dizi, harp, violin, warm nostalgic" \
  --lyrics-file episodes/<ep>/config/theme_lyrics.txt \
  --out episodes/<ep>/assets/audio/theme/suno/ --count 2
.venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_generate.py \
  --style "..." --instrumental --out ... --count 2
```

## 与其他通道的关系

- 全自动正式 API：`volc-song-gen`（火山 GenSong，经 veFaaS 中转）——优先用
- 本驱动：火山产出不符合要求（如民乐音色）时的质量上限通道
- 下载的 WAV 接入既有链路：Demucs 分离 → 对齐 → 口型（见 song-lipsync）
