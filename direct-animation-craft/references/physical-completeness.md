# 物理世界完整性验收体系（physical completeness gate）

> 目标：新集开工**一次性完整发现**物理世界合理性问题，不靠用户逐点矫正。
> 沉淀自 bio_armor_academy_s1e3 八轮修复（NOTES.md P5–P13）：失败类目已枚举完，
> 断言库已参数化，缺的只是"按类目×节拍一次性铺全"的开工方式。

## 六类失败类目

| # | 类目 | 定义 | 现有拦截手段 |
|---|------|------|-------------|
| C1 | 碰撞 | 网格互穿（门/墙/网/道具/穿戴件） | doorway / whitelist / env / worn_prop |
| C2 | 支撑 | 悬浮（物无支撑者、脚滑、盒不贴掌） | supporter / grip / check_locomotion / carry / dual |
| C3 | 生理域 | 关节/腕扭转/抬臂超限、步态滑翔 | wrist / limb_attach / gait / seated |
| C4 | 连接完整性 | 穿戴件带体断裂、容器盖不随手、交接断链 | worn_prop + 审片（连接点）/ lid / continuity |
| C5 | 接触语义 | 掌向违背动作语义（反掌送嘴）、递出指向错误 | palm_semantic / pinch / food / bite + 审片 |
| C6 | 声画同步 | 事件音与画面事件错位 | check_audio_sync（onset 对位 ±0.15s） |

## 节拍类型 × 类目覆盖矩阵

写剧本/谱面时，**每个节拍按行勾选适用断言 kind 写进 contract**；格子留空=该行该类目
不适用（要写注释说明为什么不适用，防止"忘了"伪装成"不适用"）。

| 节拍类型 | C1 碰撞 | C2 支撑 | C3 生理域 | C4 连接 | C5 接触语义 | C6 声画 |
|----------|---------|---------|-----------|---------|-------------|---------|
| 走跑 | doorway/env（路径净空） | locomotion 钉地滑移 + gait 速度域 | gait bob/步频 + limb_attach | — | — | 脚步声对位（有 Foley 时） |
| 搬运 | whitelist（托持接触行） | supporter + grip 贴掌 | wrist 托盘扭转 | — | grip 扣边 | — |
| 抓握 | whitelist（捏合接触） | 物随手（carry 类） | wrist | 交接断链=双方窗口连续 | pinch 点线域 | — |
| 放置 | whitelist（落台接触） | supporter + continuity 静置 | — | lid 盖随手动 | place 手-盒距离窗 | 落台音对位 |
| 交接 | — | supporter 双方窗口无缝 | — | continuity（物不瞬移） | pinch + 递出指向（审片） | — |
| 进食 | — | food 尖-球心/指骨不穿 | wrist | — | palm_semantic 掌心向内 + bite 到嘴 | 咀嚼音点位 |
| 坐卧 | env（矮沿/地面合法接触行） | seated 手-躯干域 | limb_attach（俯身肩缝） | — | — | 落座音对位 |
| 开关门窗 | doorway（窗口全覆盖零命中） | — | — | 门轴纯时间函数 | — | check_audio_sync 门事件 |
| 穿戴件 | worn_prop（负 margin 深穿） | — | — | 带体两端连得上（审片） | — | — |
| 情绪符号 | — | — | — | — | — | —（审片：遮挡窗口外不出现） |
| 空拍 | env/worn_prop 回归 | — | 微动不滑翔（gait 不适用时靠审片） | — | 咀嚼抬手 palm_semantic | 环境床覆盖连续 |

## 完整性定义（三条同时成立才算"物理完整"）

1. **断言绿**：contract 覆盖全部节拍的适用类目，`contact_probe.py` 零失败；
   有步态则 locomotion 绿，有混音则 audio_sync 绿。
2. **审片全**：每个道具交互事件都有近景审片组（2–3 机位），过五点清单
   （掌向/接触/支撑/连接/穿戴件）——见 physics-gate.md「逐拍近景审片协议」。
3. **声画绿**：事件音 onset 对位 ±0.15s 内。

目检只在体系报绿后做**创意层**判断（构图/表演/节奏）——物理层的目检是体系漏网的
信号，要把漏网点写回矩阵（新断言或新审片点），而不是修了就算。

## 新集开工门禁顺序

```
init_viewer_episode.py 脚手架        # viewer 链骨架 + contract/审片模板
  → 写 contract：场景障碍物清单、道具状态机、生理常量（臂长/肩高/台面高）
  → 写谱面（每个节拍按矩阵声明断言；交互相位=接触事件驱动，禁绝对时间）
  → episode_gate.py 红绿             # 不过不渲染成片
  → 逐拍近景审片（review_shots.json 随事件同步维护）
  → 成片
```

## 成本对比实录（S1E3 NOTES.md P 系列）

逐点矫正模式（用户复看一轮→修一类）共八轮：P5 穿模/桨板手/悬浮 → P6 门洞 →
P7 道具三律 → P8 手腕 → P9 声画 → P10 探针工具化 → P12 步态/肩缝/书包 →
P13 掌向/浮盒/肩桥/挎包+审片协议。每轮都含全量复渲+用户等待，类目是**串行枚举**的。

体系化后同类问题在开工门禁内并行发现：contract 铺全矩阵 → 一次渲染 trace →
19 段断言 + locomotion + audio_sync + 22 帧近景组 ≈ 两次渲染（~90s+5s）出全量报告。
失败类目在写谱面阶段定位到节拍，不活到用户复看。
