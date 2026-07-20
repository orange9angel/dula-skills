---
name: episode-scoring
description: Automatic semantic background music scoring for Dula episodes. Analyzes script.story dialogue and scene tags to decide when music should play, what mood it should have, and which track to use. Falls back to procedural placeholder loops when no curated music is available.
---

# Episode Scoring Skill

自动为 Dula episode 生成语义化背景音乐（BGM）：

```text
script.story
    ↓
MusicDirector（语义分析）
    ↓
mood timeline + music cues
    ↓
Pixabay 下载 或 程序生成占位 loop
    ↓
music_cues.json  ← dula-engine/tools/generate_audio.py 读取并混音
```

## 功能

- **语义分析**：逐句分析台词情绪，结合场景标签和角色动作判断当前氛围。
- **情绪时间线**：把连续同情绪段落合并成一段 BGM cue。
- **音乐来源**：优先使用 episode 已有的 `assets/audio/music/{mood}.wav`；没有则尝试从 Pixabay 下载；下载失败则生成一段程序化占位音乐。
- **自动生成 manifest**：输出 `assets/audio/music_cues.json`，`generate_audio.py` 可直接消费。

## 快速开始

```bash
# 从 dula-story 根目录
python dula-skills/episode-scoring/scripts/run_scoring.py ./episodes/doraemon_anywhere_door
```

这会：
1. 读取 `script.story`。
2. 生成情绪时间线和 `music_cues.json`。
3. 为每个情绪准备一段 `.wav` 音乐文件。

## 输出文件

```
episode/
├── assets/
│   └── audio/
│       ├── music/
│       │   ├── cheerful.wav
│       │   ├── tense.wav
│       │   └── ...
│       └── music_cues.json
```

`music_cues.json` 示例：

```json
{
  "version": 1,
  "generated": true,
  "cues": [
    {
      "action": "Play",
      "mood": "calm",
      "startTime": 0.0,
      "endTime": 12.5,
      "fadeIn": 1.5,
      "fadeOut": 2.0,
      "baseVolume": 0.45,
      "file": "calm.wav",
      "name": "calm"
    }
  ]
}
```

## 情绪关键词映射

| 情绪 | 中文触发词 | 英文触发词 |
|------|-----------|-----------|
| cheerful | 哈哈、开心、棒、好玩 | haha、happy、fun |
| excited | 哇、超酷、厉害、冲啊 | wow、amazing、let's go |
| sad | 呜、难过、伤心、眼泪 | sob、sad、cry |
| tense | 糟糕、快跑、危险、救命 | danger、help、scared |
| angry | 生气、讨厌、可恶、烦 | angry、hate、mad |
| mysterious | 秘密、奇怪、神奇、未知 | secret、magic、mystery |
| romantic | 喜欢、爱、心动、温柔 | love、heart、sweet |
| proud | 交给我、厉害、肯定 | of course、proud |
| calm | 别怕、慢慢来、放心 | calm、gentle、relax |

## 自定义音乐

在 `episode/config/music_registry.json` 中覆盖默认 Pixabay URL：

```json
{
  "moods": {
    "cheerful": "https://pixabay.com/music/your-custom-url/"
  }
}
```

也可以直接把同名 `.wav` 放到 `assets/audio/music/{mood}.wav`，系统会跳过下载。

## 与主流程集成

`dula-engine/tools/generate_audio.py` 在混音阶段会读取 `music_cues.json` 并自动加入 BGM 总线。

手动更新单个 episode：

```bash
python dula-skills/episode-scoring/scripts/run_scoring.py ./episodes/my_episode
python dula-engine/tools/generate_audio.py ./episodes/my_episode
```

## 程序化占位音乐

当没有可用 URL 或下载失败时，脚本会用 numpy 生成一段简单 loop。占位音乐包含：
- 根据情绪选择的大调 / 小调音阶
- 与 BPM 匹配的琶音与低音脉冲
- 紧张 / 高能量情绪会加入噪声闪光

占位音乐足以让流程跑通；想要更高质量，请配置 `music_registry.json` 使用 Pixabay 真实曲目。
