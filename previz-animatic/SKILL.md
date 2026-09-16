---
name: previz-animatic
description: Zero-cost procedural flat-vector animatic (平面预演) for any episode — validate story rhythm, VO, ambience and shot flow before spending on image/video generation. Use when the user wants a cheap draft ("先画着看看剧情配音对不对"), a parameter for painted previz, or a deliberately funny flat version.
---

# Previz Animatic（平面预演 · 零生成成本）

在生图/生视频上花钱之前，先用程序绘制的平面版把整集跑出来：
剧情节奏、配音、环境音、镜头顺序全部可验收，画面成本 ¥0、渲染全本地。
参考实现：`dula-story/episodes/cat_leads_e08_drifting_page/`（V2，2.5D 构图）。

## 什么时候用

- 新剧/新集开拍前：先听配音、看节奏、查伏笔位置，再决定要不要上生成模型
- 预算收紧时：平面版本身就是一种风格（也挺搞笑），可直接发
- 音频链路调试：口型/字幕/混音在免费画面上先验完

## 库位置

`dula-assets/lib/flatpreviz/`（纯 Canvas 2D，零依赖，浏览器直接加载）：

| 模块 | 内容 |
|------|------|
| `core.js` | 形状基元、SUNPRINT 调色板、script.story 解析、lipsync_cues 口型映射、确定性眨眼、字幕 |
| `figures.js` | 正面角色（站/惊/抱/伸手/举手/递物/坐姿速写）、表情、三态嘴型 |
| `figures-side.js` | 侧面角色（含走路循环）、后脑勺（过肩）、俯视、趴着的猫 |
| `env.js` | 天空/云/远岸/河流/草地/柳树/飞鸟/阵风粒子（河堤环境积木） |
| `driver.js` | 镜头表驱动：推拉/横移运镜、视差层速率、叠化、结尾淡出 |

## 用法（新 episode 接入）

1. 正常写 `script.story` 并生成音频（TTS + SFX + BGM，`mixed.wav`）。
2. 复制 E08 的渲染管线：`tools/render_painted.mjs`（静态服务器 +
   puppeteer 逐帧 + ffmpeg 混流，改输出名即可）、`viewer_painted.html/js`。
3. 写本集的 `painted/painter.js`：
   - 用 design 对象声明角色（肤色/发色/衣服/发型 bob|spikeV/dress/iris/clip）
   - 用 env.js 积木搭场景，用 figures 摆人物
   - SHOTS 镜头表：`{ at, paint(ctx,t,data,cam), move, transition }`
   - `makeDriver({shots, duration, W, H, labels, fadeAt})` 出 `paintFrame`
4. `--check` 出逐镜头检查帧 → 目检 → 正式渲染。

口型零成本复用：`lipsync_cues.json` 按**角色名**绑定（不要绑镜头），
侧面/正面/特写都能吃同一份数据。

## 纪律

- **这是预演，不声称成片质感**。验收对象是剧情/配音/环境音/镜头顺序，
  不是画面精度。文档里别写"达到生成模型水平"。
- 伏笔符号同样适用隔离纪律：画页/道具上不许出现 reveal 镜头才有的符号
  （程序绘制也一样——公共 prop 画法里不要顺手把伏笔画进去）。
- 有限动画诚实原则：没有的动作（走路转身之外的复杂表演）不要假装有；
  情绪靠表情切换、姿态切换和镜头切换。
- 视差层速率：天 0.12 / 远岸 0.35 / 水 0.6 / 前景 1.0；横移运镜 zoom 必须
  >1（约 1.08）盖住两侧边缘。
- 侧脸翻车教训：刘海三角挂到额头中间会读成愤怒眉毛——侧脸刘海贴发际线，
  眼睛放大到 0.19×头半径，眉毛 0.07 线宽。
- 读图用量纪律（不禁止参考图，只控量）：画法知识优先从本库代码与本文件
  文字记录取；参考图/检查帧按需少量读取（一次任务几张以内、先缩略图），
  避免大量读图触发 Kimi 5 小时滚动限流窗口（2026-09-16 E08 V2 教训）。

## 翻车记录

- 2026-09-15 E08 V2：正面画法刘海向上长刺读作猫耳；改为沿发际线向下的
  V 形刘海。裙子要有明确的色块主体（蓝背带裙），否则白 T 恤吃掉整个躯干。
