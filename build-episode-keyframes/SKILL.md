---
name: build-episode-keyframes
description: 程序化绘制剧集位图——手写 SVG/矢量形状经 Puppeteer 转 PNG，产出风格测试、场景、关键帧与 on-twots 动作 cel。用于画风是平涂/零纹理/固定色板（如"晴印"Sunprint）、要求角色代码级一致性、或不想消耗任何文生图配额时。需要神经网络画味的镜头走 build-continuous-story-images 的 DashScope 轻量通路。
---

# Build Episode Keyframes（程序化绘制）

**自己画关键帧**：不调用任何文生图模型，手写矢量形状（SVG）经 Puppeteer 截图为
PNG，接入各剧集现有点图管线。后处理（diff-lock、场景代码、crop 运镜、音频）与
imagegen 产物完全一致，零适配成本。

## 为什么可行

晴印类画风的五要素（锐边平涂、零纹理、固定色板、互补色阴影、形状阳光）全是
确定性图形语言——这正好是代码擅长、而文生图反而容易漂移的部分。

- **角色一致性代码级**：角色定义为参数化矢量组件（"矢量木偶"），身份锁在代码里，
  每一帧都是同一个角色，不靠参考图赌概率
- **动作连贯性靠参数插值**：每帧 = 一组姿态参数（走路相位、头部转向、口型/眨眼
  状态），on twos / 任意帧率批量渲染
- **零配额**：不碰 Codex 订阅额度，也不产生 API 费用

## 与文生图通路的分工

| 镜头类型 | 通路 |
|----------|------|
| 动作 cel（走路循环、姿态序列、口型/眨眼） | 本 skill（程序化） |
| 建立镜头、复杂构图、画味要求高的母版 | `build-continuous-story-images` 的 DashScope 轻量通路（`scripts/gen_image.py` / `gen_batch.py`） |
| 订阅额度内的零边际成本兜底 | Codex imagegen（见 build-continuous-story-images/references/codex-cli-imagegen.md） |

## 渲染工具

SVG → PNG 走 dula-engine 已有的 Puppeteer 依赖，无新增依赖：

```bash
node tmp/rasterize.js <input.svg> <output.png> [width=1672] [height=941]
```

（`tmp/rasterize.js` 现为 pilot 脚本；路线确认后提升为 `scripts/` 正式脚本，
角色/场景组件库放 `lib/`。）

## 已验证

- `tmp/pilot_frame.svg` → `tmp/pilot_frame.png`（1672×941）：晴印五要素全部成立
  （两段色天空、硬边泡泡云+紫投影、金色光斑、紫色地面树影、零纹理平涂）。
- 已知短板：角色形状语言粗糙（头发成团、格裙线条糙、比例僵），需要按
  "矢量木偶"方式迭代——这是本路线的主要投入点。

## 生产纪律

1. 色板、阴影规则、阳光形状严格对齐剧集 STYLE_BIBLE，不发明新色。
2. 场景与角色分层绘制：背景一图一画，角色 cel 全部走参数化组件，禁止逐帧手改形状。
3. 每帧渲染后目检（ReadMediaFile），重点查轮廓穿插、层级遮挡、投影位置。
4. 产出的 PNG 规格与 imagegen 产物一致（1672×941 级别），后续 crop 运镜、
   口型调度、diff-lock 工具原样复用。
5. 翻车写回：形状语言、组件参数设计的教训写回本 SKILL.md 或 references/。
