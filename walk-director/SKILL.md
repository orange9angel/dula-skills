---
name: walk-director
description: 走路、后退、起停与转身的制作和验收。用于 2D 换脚 cel 与跟走镜头、3D Event:Move 步速匹配，以及程序角色/IK 的有限落脚、支撑锁定和重心协调；诊断滑步、交叉腿、碎步、朝向错位、停步跳变与背景互闪。包括同机位试片、实际接触轨迹和顺序/seek 验证。
---

# Walk Director

走路镜头专项规范。本 skill 放 `dula-skills/walk-director/`；产物只写到
`dula-story/episodes/<episode>/`（`config/walk_segments.json`、
`config/keyframe_timeline.json`、`assets/action_inbetweens/` 的走路 cel、
以及 3D 剧集的跟走运镜、程序步态与检查记录）。

按实际运行入口选择管线：

- **2D 关键帧管线**（`*SequenceScene.js` + `config/keyframe_timeline.json`）：
  走路有两种做法，先选型再动手（见 keyframe-walk-shots.md「选型」节）：
  - **连续换脚**：A/B 触地 cel 交替 + `walk_follow` 连续平移 + `motionGroup`
    整组进度采样。前提是 cel 对能做到背景/上半身像素级一致（v10 工艺）。
  - **静帧规避**（cat_leads frame_06 段实证）：单帧 + 运镜（背影走远用
    `walk_away` 缓拉远），或**近/远两张静帧硬切**（同机位、人缩小走远）
    表现"走了一段"。cel 无法像素级锁定时用这个，不要硬上 A/B。
- **3D 管线**（`.story` DSL + 低模角色）：走路 = `{Event:Move}` 自动并播 Walk
  动画 + 跟随运镜；步频/位移必须手动匹配，否则滑步。
- **自有 3D/IK 管线**（独立 viewer + 程序角色）：按路径排有限落脚，协调根位移、
  躯干和手脚，分别处理起步、收步及原地转身；导出实际模型接触轨迹验收。
- **3D底稿转二维作画**：优先从实际全身步态导出关键姿势，再做整人物cel和有限
  修型，见[整集作画的步态修订](../draw-over-animation/references/full-episode-direction.md)。
  图片拆腿只有在重心、肩胯、膝踝和接触的连续画面成立时才可用；“像折纸戏”的
  反馈不能靠增加腿部控制点消解。底稿和作画的步相/根轨迹共同重定时。

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
- 整人物二维原画需要限定机位的局部腿控制时，复用
  [draw-over-animation 的腿层与支撑目标](../draw-over-animation/references/full-episode-direction.md)。
  先分离腿与披风/手臂，检查新露出区域；目标锁定不代替实际鞋底连续帧验收。
- 3D 管线（`Event:Move`、跟走运镜选型、步速匹配公式、平滑 Follow 模板）：读
  [references/story-dsl-walk.md](references/story-dsl-walk.md)。
- 剧集自有程序角色、IK 或独立 viewer：读
  [references/procedural-footsteps.md](references/procedural-footsteps.md)，检查左右脚轨道、
  朝向、有限步数、起停与转身。不要假定该管线会执行 `Event:Move` 或共享 Walk。
- 可执行步态引擎：有限落脚步态已晋升为共享资产 `dula-assets/lib/craft3d/locomotion.js`
  （`createLocomotion(params)` 参数化，默认值=S1E2 验收值；换角色需重测比例、落脚与重心）。
- 手脚以外的接触（手-门/桌/道具、进食送嘴）与防穿模数值断言：读
  [direct-animation-craft/references/contact-and-hands.md](../direct-animation-craft/references/contact-and-hands.md)。
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

## Workflow（自有 3D/IK 管线）

读取 [程序角色有限步态](references/procedural-footsteps.md)。先保存基线和同机位
短片，再检查前向、左右足轨道、步长定义、末步及转身接触；按角色比例和性格
调整，复核实际世界脚位、鞋朝向、骨长和鞋底，最后接回原镜头与音轨。
该 skill 提供制作与验收方法；参考代码目前在 S1E2，尚未发布为共享动作资产。

速度剖面纪律（S1E3 P12 实录）：**别用 ease 驱动步行根位移**——ease 中段瞬时
速度=1.5×段均值，小个子角色走成"赶路机器人"（雷晓 7.5m 走廊 p50 1.85/max 2.84 m/s
翻车）。用梯形剖面（线性 ramp ≈12% + 中段匀速，峰值≈1.14×均值），walkingFeet 的
落脚跟随根投影，步频随速度自然变化、无需另调。角色步幅用 `strideFactor`（乘在
stride 上）做 persona：小个子 0.85 短步稳频，大个子保持大步快走。停步张望用
显式 pause 段（walk=null 站立帧），比放慢整条走廊更读得出"心虚"。数值门禁走
direct-animation-craft 的 `gait` 段（速度上限/均速下限/bob 振幅下限/步频域）。

## Validation

人形直立纪律（2026-10 stardust_clad_op R7"山羊腿"整改实录）：走路读成山羊腿/
蹲行的根因通常是**髋高目标恒低于腿长允许的 cap**，双膝全程深屈。修法三件套：
① 站姿/走姿把髋部目标抬到贴近 `footY+√((legA+legB-ε)²−水平距²)` 的 cap（支撑相
伸直、迈步转换点下沉——用 locomotion 的 hipDelta 放大到 ~.04 而不是 .008）；
② 需要整体更挺时把 hipY 与躯干 bob 同加一个 standStraight 常数（只抬髋不抬躯干
会让腿根穿出骨盆；臂链肩点与腕目标同加，reach 探针零影响）；③ 双臂对摆必须
**门控垂挂臂**——抬臂架势（格斗/踉跄）叠加摆动会把腕点顶过 reach .9 阈，按前臂
抬角线性收掉（>32° 归零）。跑步与步行分流成两个 createLocomotion 实例（run=
更高 lift/更大摆臂），别动共享默认值（s1e2/s1e3 已验收在用）。

自有 3D/IK 管线先按 `procedural-footsteps.md` 导出实际世界脚位、鞋朝向与接触段，
做局部顺序渲染和同机位对比；下面的 cel 验收项只适用于 2D 关键帧管线。

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
