---
name: credits-sequence
description: 漫威式片尾生成器——Ken Burns 概念美术蒙太奇 + xfade/光闪转场 + 右侧竖栏滚动演职员表 + 片尾曲自动裁剪淡出。零生成费（PIL+numpy+ffmpeg）。用于给完成的短片/剧集追加片尾与彩蛋。
---

# Credits Sequence（漫威式片尾）

给成片追加 20-40s 片尾：未采用素材（设定图/母版/废弃关键帧）做概念美术
蒙太奇，右侧竖栏滚动演职员表，片尾曲垫底。片尾曲用 Suno（suno-driver）
或火山 GenSong（volc-song-gen）生成。

## 用法

```bash
PY=dula-story/.venv/Scripts/python.exe
$PY dula-skills/credits-sequence/scripts/make_credits.py \
  --images <图1> <图2> ... \
  --audio <片尾曲.mp3> \
  --credits <credits.json> \
  --duration 30 --out <credits.mp4>
```

`credits.json`：`[{"role": "角色设计", "name": "..."}, ...]`——role 用细体
小字、name 用楷体，建议 10-14 行，技术岗位可写模型名（声の出演=Seed-Audio、
作画=codex imagegen、动画=Seedance），既是字幕也是技术签名。

## 结构纪律

- 图片 6-10 张，每张 3-4s，Ken Burns 推/拉交替；相邻段 0.6s 交叉淡化；
  中段加一次 2 帧光闪提节奏。图必须是**未在正片出现的素材**（概念美术感），
  不要复用正片镜头。
- 滚动字幕走**右侧竖栏**（漫威排版），不要居中全屏滚——画面才是主角。
- 片尾曲裁到目标时长，结尾 2.5s 淡出。

## 彩蛋（可选，接在片尾后）

漫威钩子的程序化做法（参考《9章》序章）：取正片 establishing 帧，
PIL 在关键位置做青绿光脉冲（距离场呼吸，2 次）+ 心跳 SFX + 环境音骤停 +
淡黑，1.5-3s。埋季终钩（如"后山坠坑仍在发光"），零生成费，比重生成一个
镜头便宜且更克制。
