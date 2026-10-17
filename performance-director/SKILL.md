---
name: performance-director
description: Optimize facial expressions and body actions in a Dula script.story based on dialogue semantics, subtext, and character voice. Runs as a post-processing step after story-writer and before scene-designer/audio/render.
---

# Performance Director

`performance-director` 是 `story-writer` 之后的表演优化层。它读取已有剧本，根据台词语义、潜台词、角色性格和上下文，优化表情 (`Animation:FaceXxx`) 和动作 (`{Action}`) 标签，让动画表演更生动、有层次。

## 先确认表演由哪一层执行

本技能的规则脚本修改 DSL 标签。若 episode 使用自包含 viewer、姿态求解或面部纹理
驱动，先确认这些标签是否被实际消费；不要把添加标签当成运行时表演已经改变。
用户指出成片僵硬、格斗无力或与商业动画有差距时，结合最终视频检查实际表演代码，
转用 [动画作画监督](../direct-animation-craft/SKILL.md)。双人格斗及试片接正片的
具体做法见 [格斗表演与正片接入](../direct-animation-craft/references/fight-performance.md)。
下文角色和动作仅作标签流程示例；应用时沿用用户当前剧集、人物与既有资产。

## 定位

```
story-writer          →  故事骨架、对话、时间轴、基础事件
performance-director  →  表情、动作、反应镜头
scene-designer        →  空间、场景、镜头、站位
episode-scoring       →  BGM
f5-tts-voice          →  配音
```

## 边界

- **不改**：台词文本、时间轴、场景切换、`{Event:...}`、`{Position:...}`、`{Camera:...}`、`{Music:...}`、`{SFX:...}` 等非表演标签。
- **改**：`[Speaker]{Action}` 中的动作、`{Animation:FaceXxx|character=...}` 表情。
- **可增**：反应镜头的动作/表情、表情过渡标签、眨眼/重置标签。
- **只使用已注册资产**：运行前必须通过 `story_tool.py catalog` 确认本 episode 可用的动画和表情。

## 输入输出

```bash
# 从 dula-story 根目录运行
python ../dula-skills/performance-director/scripts/run_director.py \
  ./episodes/tom_jerry_midnight_snack \
  --output ./episodes/tom_jerry_midnight_snack/script.story.perf
```

- **输入**：`episodes/<name>/script.story`
- **输出**：`episodes/<name>/script.story.perf`（默认后缀 `.perf`）
- 满意后手动覆盖原文件：
  ```bash
  mv ./episodes/<name>/script.story.perf ./episodes/<name>/script.story
  ```

## 核心策略

### 1. 表情分层

不要只看台词表面情绪，要识别潜台词：

| 表面情绪 | 潜台词 | 推荐表情 |
|---|---|---|
| 开心 | 得意、试探 | `FaceSmirk` |
| 开心 | 真诚 | `FaceHappy` |
| 生气 | 强压怒火 | `FaceDetermined` |
| 生气 | 爆发 | `FaceAngry` |
| 惊讶 | 害怕 | `FaceSurprised` |
| 惊讶 | 疼痛/狼狈 | `FacePain` |
| 拒绝 | 轻蔑 | `FaceSmirk` |
| 困惑 | 真的不懂 | `FaceConfused` |
| 悲伤 | 失望 | `FaceSad` |
| 长时间说话 | 需要眨眼/重置 | `FaceBlink` / `FaceReset` |

### 2. 动作节拍

根据台词节奏和剧情位置分配动作：

| 场景位置 | 动作策略 |
|---|---|
| 开场/建立 | 小动作：`LookAround`、`Nod`、`CrossArms` |
| 挑衅/谈判 | 手势动作：`PointForward`、`HandsOnHips`、`CrossArms` |
| 追逐/冲突 | 大动作：`CatPounce`、`MouseScamper`、`CatCatchStack` |
| 失败/狼狈 | 滑稽动作：`CatSkid`、`FlailArms`、`Tremble` |
| 反应镜头 | 无台词：`ShakeHead`、`SurprisedJump`、`CatDoom` |

### 3. 角色特化

同一句话，不同角色应有不同表演风格：

- **Tom（猫）**：傲慢 → 狼狈 → 气急败坏
  - 得意时用 `FaceSmirk` + `CrossArms`
  - 被耍时用 `FaceSurprised` + `CatSkid`
  - 发怒时用 `FaceAngry` + `CatPounce`
  - 失败时用 `FacePain` + `FlailArms`

- **Jerry（老鼠）**：机灵 → 得意 → 挑衅
  - 试探时用 `FaceSmirk` + `MouseOffer`
  - 得意时用 `FaceHappy` + `MouseTaunt`
  - 挑衅时用 `FaceDetermined` + `CartoonShush`

### 4. 表情过渡

长台词或情绪转折处，可以拆分表情：

```text
[Jerry]{MouseOffer}{Animation:FaceSmirk|character=Jerry}见面分一半？
```

如果下一句 Tom 拒绝得很刻薄，Jerry 可以逐渐从 `FaceSmirk` 转为 `FaceDetermined`：

```text
[Jerry]{MouseTaunt}{Animation:FaceDetermined|character=Jerry}那我自己拿。
```

## 运行流程

1. 读取 `script.story`
2. 运行 `story_tool.py catalog` 获取本 episode 可用动画/表情
3. 逐句分析台词语义、情绪、潜台词
4. 根据角色特化规则选择表情和动作
5. 生成 `script.story.perf`
6. 运行 `story_tool.py validate` 验证

## 验证

生产目标是稳定快速成片。防穿模不能通过冻结听者、缩掉关键手势达成；S1E4 R1
正因这两点被用户否决。给每个关键转折安排主动作和听者反应，并确认最终 runtime
确实消费这些通道。检查真实腕点、头转向与注意力变化，不能只检查事件名或口型。
适当停顿可保留，不能用持续正弦晃动或最低速度指标伪装表演。先验证代表性短片再铺整集。

### 双人对白的视线验收

- S1E4 写有 `gaze=partner`，最终头部正前向却仍偏离对方约 50–70 度，
  眼珠位移又很小，用户看到的是朝镜头轮流念台词。目标标签和变化幅度都不能
  证明眼神交流；检查实际世界空间眼位、头部朝向、眼球残余转角与最终画面。
- 每个交流节点明确注意对象：对方、伤处或道具。眼睛先转、头部稍后跟随，
  肩和点头只在需要回应时参与；听者也要有等待、接话、领会或避开目光的节拍。
  这些变化用故事时间的确定函数实现，避免上一帧累积导致 seek 漂移。
- 让角色实际看对方后，检查原机位是否反而拍到后脑。说话人的特写从能看到
  面部的一侧安排，保持双方屏幕视线方向及对话轴；同时检查背景板边界和裁切。
  中性转台通过不能替代带对白的双人镜头，角度指标通过也不等于表演被接受。

优化后必须验证：

```bash
cd dula-story
python ../dula-skills/story-writer/scripts/story_tool.py validate \
  --story ./episodes/<episode>/script.story.perf \
  --episode-dir ./episodes/<episode>
```

## 未来升级

当前是**规则版**（轻量版），按关键词和角色映射表情/动作。后续可以升级为：

- **LLM 版**：调用大模型做更 nuanced 的语义分析
- **组合表情**：支持 `FaceHappy` + `FaceSmirk` 叠加
- **动作链**：自动生成 `CatSneak` → 停顿 → `CatPounce` 的动作序列
