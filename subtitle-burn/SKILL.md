---
name: subtitle-burn
description: 字幕组风格双语字幕——事件 JSON 生成字幕组风 ASS（角色自动分色、黄色英文副字幕、片头字幕组卡、淡入淡出），可选 ffmpeg 直接烧入视频。用于给成片加专业字幕组风格的中英双语字幕。
---

# Subtitle Burn（字幕组风格双语字幕）

好莱坞大片 MKV 里那种专业字幕组风格：雅黑粗体白字主字幕（按角色分色）、
黄色英文副字幕、片头字幕组水印卡，ASS `\fad` 淡入淡出。

## 用法

```bash
PY=dula-story/.venv/Scripts/python.exe
$PY dula-skills/subtitle-burn/scripts/make_subs.py \
  --events subs.json --ass-out subs.ass \
  --video clean_master.mp4 --out-video final.mp4   # 可选：直接烧入
```

`subs.json`（**英文行由代理翻译填写**，工具不做机翻）：

```json
{
  "group": "Dula 字幕组",
  "project": "9章 PROJECT · 序章",
  "events": [
    {"start": 0.3, "end": 5.3, "speaker": "雷晓",
     "cn": "白……岚……部……长……", "en": "Bai... Lan... Cap... tain..."},
    {"start": 5.3, "end": 10.35, "speaker": "白岚",
     "cn": "学生会命令：9章，今晚回收。",
     "en": "By order of the Student Council: Chapter 9 — retrieved tonight."}
  ]
}
```

- `speaker` 按出场顺序自动分配分色盘（淡金/淡青/淡绿/淡粉/浅橘/淡紫）
- `group`/`project` 留空则不出片头卡
- 单事件可加 `"fade": "300,500"` 自定义 `\fad`

## 纪律（全是踩过的坑）

- **字幕只烧进净版母带**：已烧过字幕的版本上叠烧 = 双重字幕。任何后期
  （字幕/转场/贴字）都从净版出。
- 非语言嘶吼、旁白框、片尾曲、彩蛋区**不加字幕**。
- 测试渲染效果时用**输出寻址**（`-ss` 放输出位），输入寻址会把滤镜时间轴
  归零、ASS 事件全部"未激活"，误判为没渲染。
- ffmpeg ass 滤镜传 Windows 路径必须转义盘符冒号（脚本已内置处理）。

参考实现：`dula-story/episodes/bio_armor_academy_s1e1/config/fight_subs.ass`
（《9章》序章，本 skill 输出与其同风格）。
