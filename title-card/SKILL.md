---
name: title-card
description: 程序化转场字卡/章节卡生成器——墨韵侵蚀标题（楷体+噪声场阈值侵蚀+前沿辉光+飞白纹理）+ 光效（白光切镜/对角光扫/bokeh/白光爆发或淡黑切出），底图可配。零生成费（PIL+numpy）。用于镜头间转场桥（遮住瑕疵区/叙事跳切）、开篇卡、结束卡。
---

# Title Card（程序化转场字卡）

AI 镜头出畸变或需要叙事跳切时，**剪辑补丁优于生成重赌**：挖掉坏区，
字卡过桥（前帧抛体 → 字卡 → 后帧落地，卡在叙事上就是那个动作）。
也用于开篇/结束卡。零生成费，秒级出片。

## 用法

```bash
PY=dula-story/.venv/Scripts/python.exe
# 中间转场卡（白光爆发切出）
$PY dula-skills/title-card/scripts/make_title_card.py \
  --bg <底图.png> --title "9章" --subtitle "残卷 · 其一" \
  --duration 1.2 --reveal 0.18,0.62 --out-mode white --out-dir tmp/card_frames
# 结束卡（淡黑收尾）
$PY dula-skills/title-card/scripts/make_title_card.py \
  --bg <底图.png> --title "9章" --subtitle "序章 · 完" \
  --duration 1.7 --reveal 0.15,0.85 --out-mode black --out-dir tmp/card_frames
# 帧序列 → mp4
ffmpeg -framerate 24 -i tmp/card_frames/f_%03d.png -c:v libx264 -pix_fmt yuv420p -crf 18 card.mp4
```

参数：`--title-size`（默认 200）、`--title-y`（纵位比例）、`--seed`
（墨韵噪声种子，换 seed 换侵蚀形状）。

## 工艺要点

- 底图自动虚化 6 + 暗化 + 1.0→1.06 缓推（Ken Burns）。
- 标题：STKAITI 楷体 mask + numpy 多倍频噪声场阈值侵蚀（字从墨韵中长出）、
  前沿青绿辉光、飞白干笔纹理。黑体做不出墨韵，必须用楷体类。
- 光效全程序化：白光切镜、对角光扫（additive）、bokeh 光斑上浮、
  出场二选一（白光爆发 / 淡黑）。
- **PIL 两坑**：RGBA 画布上 ImageDraw 是像素替换不是混合（淡入淡出必须
  `Image.blend` / `ImageEnhance`）；`alpha_composite` 产生新图后旧 Draw
  对象失效（先复合完再建 Draw 画字）。
- **补丁永远从净版母带出**，禁止从已补丁版本叠补丁。

参考实现：`dula-story/episodes/bio_armor_academy_s1e1`（《9章》序章
中间卡 + 结束卡）。
