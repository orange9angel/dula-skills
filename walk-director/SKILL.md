---
name: walk-director
description: 走路/移动镜头的创作与验收规范。Use when an episode needs a character to walk or travel on screen — choosing and accepting walk-cycle cels (A/B 触地互换), deciding between 连续换脚 vs 静帧运镜/近远两拍（walk_away 拉远）, making the camera actually follow the movement (2D `walk_follow` + `motionGroup` crop pan, or 3D `Event:Move` + follow camera), building or rebuilding walk segments in `config/keyframe_timeline.json` from `config/walk_segments.json`, validating walk groups, or diagnosing 原地踏步感、往返抖动、滑步、换腿不可读、背景互闪/身体拼接断裂、dula-verify 走路盲区等问题。
---

# Walk Director

走路镜头专项规范。本 skill 放 `dula-skills/walk-director/`；产物只写到
`dula-story/episodes/<episode>/`（`config/walk_segments.json`、
`config/keyframe_timeline.json`、`assets/action_inbetweens/` 的走路 cel、
以及 3D 剧集 `bootstrap.js` 里的自定义跟走运镜）。

覆盖两条管线：

- **2D 关键帧管线**（`*SequenceScene.js` + `config/keyframe_timeline.json`）：
  走路有两种做法，先选型再动手（见 keyframe-walk-shots.md「选型」节）：
  - **连续换脚**：A/B 触地 cel 交替 + `walk_follow` 连续平移 + `motionGroup`
    整组进度采样。前提是 cel 对能做到背景/上半身像素级一致（v10 工艺）。
  - **静帧规避**（cat_leads frame_06 段实证）：单帧 + 运镜（背影走远用
    `walk_away` 缓拉远），或**近/远两张静帧硬切**（同机位、人缩小走远）
    表现"走了一段"。cel 无法像素级锁定时用这个，不要硬上 A/B。
- **3D 管线**（`.story` DSL + 低模角色）：走路 = `{Event:Move}` 自动并播 Walk
  动画 + 跟随运镜；步频/位移必须手动匹配，否则滑步。

## Boundaries

- 走路 cel 的**通用生图流程**（参考链管理、provider 细节、锁定区贴回）归
  `build-continuous-story-images`，本 skill 复用其 [walk-cycles.md](../build-continuous-story-images/references/walk-cycles.md)。
  **换腿专用的 prompt 控制写法**（viewer 视角、等幅反相、分离度量化）归本
  skill，见 references/keyframe-walk-shots.md 的「换腿 prompt 控制」节。
- 不改 `dula-engine` / `dula-assets`。需要平滑跟走运镜时，把模板类复制进剧集
  自己的 `bootstrap.js` 注册（见 references/story-dsl-walk.md）。
- 剧本、音频、口型归 story-writer / direct-episode-audio；本 skill 只动
  时间线中的走路段。

## Load Context

- 2D 走路镜头的完整机制与翻车史：读
  [references/keyframe-walk-shots.md](references/keyframe-walk-shots.md)（**动手前必读**）。
- cel 相位生成顺序与逐张验收清单：读
  [build-continuous-story-images/references/walk-cycles.md](../build-continuous-story-images/references/walk-cycles.md)。
- 3D 管线（`Event:Move`、跟走运镜选型、步速匹配公式、平滑 Follow 模板）：读
  [references/story-dsl-walk.md](references/story-dsl-walk.md)。
- 验收方法（短渲抽帧、dula-verify 盲区）：读
  [references/verify-walk-shots.md](references/verify-walk-shots.md)。
- 先看剧集现状：`config/keyframe_timeline.json` 里带 `motionGroup` 的帧就是
  现有走路段；`config/walk_segments.json`（若有）是它们的可重放来源。

## Workflow（2D 关键帧管线）

从 `dula-story` 根目录运行所有命令。

1. **定镜头边界与步态。** 在剧本/分镜里确定每段走路的 `[start, end)`、机位
   （远景侧景 / 背影 / 正面走近）、行走方向，以及**步态风格**（轻快 /
   蹒跚 / 拖沓——决定 cel 姿态、rate 和平移速度，见
   keyframe-walk-shots.md「步态风格」节）。边界同时写进 storyboard.md，
   不要只散落在工具脚本的魔法数字里。
2. **选/生成 cel。** 每段走路用**该镜头专属**的同构图全幅 cel 对
   （触地A ↔ 触地B），相位差必须全尺寸可读；背影镜头要做得比侧景更夸张。
   选择标准与**换腿 prompt 控制写法**见 keyframe-walk-shots.md 的
   「cel 选择」「换腿 prompt 控制」两节。入库到
   `assets/action_inbetweens/`。
3. **声明分段。** 写 `config/walk_segments.json`：

   ```json
   {
     "version": 1,
     "segments": [
       {
         "group": "street_walk",
         "start": 10.0, "end": 12.5,
         "rate": 3.2,
         "move": "walk_follow",
         "cels": [
           {"file": "keyframes/frame_04.png", "shot": "street_walk_contact1"},
           {"file": "action_inbetweens/frame_04_walk_alt_full-v4.png", "shot": "street_walk_contact2"}
         ]
       }
     ]
   }
   ```

   有眨眼 rig 的正面镜头加 `"eyeRig": "<rig 名>"`（跨 cel 的 `blinkCarry`
   由工具自动写）。`cloudDrift/dappleSway/steam/doorBand` 自动从区间内
   现有模板帧继承，不用抄进配置。
4. **展开时间线。**

   ```bash
   python ../dula-skills/walk-director/scripts/build_walk_timeline.py ./episodes/<episode>
   ```

   工具把 `[start, end)` 内的帧替换为等间隔 A/B 交替 beats，全部带
   `motionGroup` + `walk_follow`，保持一行一帧格式。`--dry-run` 先看帧数变化。
5. **验证。**

   ```bash
   python ../dula-skills/walk-director/scripts/validate_walk.py ./episodes/<episode>
   ```

6. **抽帧验收。** 按 verify-walk-shots.md 短渲走路区间并抽帧，逐镜头核对
   验收清单。**不要**只靠 `npx dula-verify`——它的采样点结构性落在走路段之外。

## Workflow（3D 管线）

```
[Name]{Event:Move|character=Name|x=..|z=..|duration=..}{Camera:FollowCharacter|target=Name|offset=..}
```

`Event:Move` 自动并播 Walk 动画；按 references/story-dsl-walk.md 的步速公式
匹配 `duration` 与 Walk 的 `frequency/stride`，需要平滑跟随时复制模板运镜类进
`bootstrap.js`。

## Validation

```bash
# 时间线结构 + 走路组验收（从 dula-story 根目录）
python ../dula-skills/walk-director/scripts/validate_walk.py ./episodes/<episode>
# 全剧集门禁
npx dula-verify ./episodes/<episode>
```

`validate_walk.py` 通过 ≠ 观感合格；观感以短渲抽帧为准（verify-walk-shots.md）。

## Acceptance bar

- 每段走路：≥2 张同构图全幅 cel、相邻帧相位必不同、组内 cel 像素尺寸一致、
  驻留 ≥0.15s。
- 所有 `motionGroup` 帧 `move` 为 `walk_follow`（或同原理的连续平移预设），
  **不得为 `static`**——那是 V4 抖动期的临时回退，静止机位 = 原地踏步感。
- 平移方向与角色行走方向一致；crop 进度整组连续（逐 cel 不重启）。
- 带 eyeRig 的走路组 `blinkCarry` 连续，抽帧确认眨眼跨 cel 无跳变。
- `config/walk_segments.json` 与 `keyframe_timeline.json` 同步：重跑
  `build_walk_timeline.py` 后时间线无 diff。
- 抽帧验收覆盖每一段走路的起点附近与跨 cel 切换点。

## 与未来图生视频（I2V）的关系

当前用图片序列是因为 I2V 成本不可接受；本 skill 的设计按"将来可换介质"
分层，迁移时不是重写而是换实现层：

**介质无关、继续有效**（写进规格与验收，不绑定 cel 概念）：

- `walk_segments.json` 就是**走路镜头规格书**：起止、机位、方向、步态
  persona、速率。I2V 时代它就是生成请求的输入，字段不用改。
- 步态 persona 参数、步频/步幅/平移速度匹配公式、方向匹配、落地影随脚、
  声画同步交接、镜头边界与抽帧验收清单——换成视频后验收项从"换腿可读"
  换成"步态自然无滑步"，检查点不变。
- prompt 控制经验（viewer 视角逐字写腿位、锁上半身、等幅反相）大部分
  可直接搬进 I2V 的 motion prompt。

**图片序列专属、I2V 后整层替换**：

- A/B cel 展开（`build_walk_timeline.py` 的 beats）、`motionGroup`、
  `walk_follow` crop 平移、`blinkCarry`。
- 替换点在**合成阶段**，不在播放器：管线本来就是"渲帧 → ffmpeg 合成"，
  I2V 后走路段的 cel beats 被一条视频片段取代，合成时把对应区间的帧换成
  该片段即可，场景播放器无需改动。
- 跟走运镜从 crop 预设变成 I2V 的 motion prompt 语言（"镜头跟随角色向右
  平移"），方向/速度匹配规则照旧生效。
- 唯一要检查的交界：I2V 段内原本由引擎侧绘制的东西（字幕、口型/眨眼
  rig、程序化光影层）要么交给视频模型自己生成，要么在合成阶段补叠——
  走路段带台词时尤其注意字幕别丢。

**纪律**：新增走路知识时先问"这条规则在视频介质下还成立吗"，成立的写进
规格/验收层，不成立的明确标注"图片序列专属"。
