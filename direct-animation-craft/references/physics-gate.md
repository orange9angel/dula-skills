# 编写期物理门禁（physics gate）

物理错误（穿模、悬浮、空手托盘、超臂长目标）不该活到渲染后由用户复看发现。
本门禁把它前置到写谱面阶段：探针当编译器用，不过不渲染。工艺沉淀自
bio_armor_academy_s1e3（《9章》S1E3，14 段断言全绿后用户零物理类反馈）。

## 三层防线

1. **生理域常量表 + 可达性**：写 IK 目标点之前先过可达性——肘腕目标必须在臂长
   球壳内（够不着就报错，不要静默 clamp：S1E3 实录"扶盒沿点"超臂长被 clamp 后
   手悬空；坐姿肩高 1.16m/台面 0.58m/臂长 0.43m 时，身侧台面必须带 lean 俯身才够得着）。
   常量表：腕扭转 ±60°、掌法向量⊥前臂轴、手-躯干轴距离域、步幅/落脚域
   （数值见 [contact-and-hands.md](contact-and-hands.md) 与
   [walk-director](../walk-director/SKILL.md) 的已验收实测）。
2. **姿势由道具状态机派生**：hidden→held→placing→down，状态转换只发生在手接触
   事件；空手回静息。手写"姿态约束挂角色"会泄漏（S1E3 实录：放下盒后手仍托盘状、
   盒盖无人自己开）。
3. **探针当编译器**：`contact_probe.py` 红绿优先于渲染抽帧——先写 contract
   （障碍物/道具/窗口/阈值/白名单），trace 出来先过探针再看画面。

## trace 契约（viewer 侧探针输出）

viewer 的 draw state 按帧输出以下键，contact_probe.py 按 contract 消费：

| 键 | 内容 | 产出段 |
|---|---|---|
| `contact.hands` | 各角色左右手世界坐标 | seated/carry/tray/supporter/place/dual |
| `contact.doorA` 等场景件位姿标量 | 纯时间函数的场景状态 | doorway（网格段由 viewer 侧 probe 模块产出） |
| `doorway`（probe-door） | `{margin,counts,skinnedCounts,obstacles,hits}` 三角相交 | doorway |
| `bento`（probe-bento） | 同上 + `positions`（道具盒世界位） | whitelist/dual/place/continuity |
| `env` | 环境障碍（铁丝网薄板代理等）相交 | env |
| 食物/嘴/签尖/掌心/腕审计/托盘强度/盖角与盖把手距 | contact.nug/nugBoneMin/skewerTip/skewerPos/palm/wrist/trayK/lidAngle/lidTabDist/boxPos/boxVis | food/pinch/wrist/tray/lid/supporter |

probe 查询串约定：`render.mjs --q "&probe-door=1&probe-bento=1"`；探针模块惰性
import（不进正片渲染路径）。15Hz 姿势帧（一拍二）下的道具连续性按姿势帧比较，
别按输出帧（S1E3 实录：输出帧级位移会误报一拍二的正常走步）。

## 工作流门禁

1. 写谱面 → `contact_probe.py`（contract 先行）红 → 改谱面/道具路径 → 绿。
2. 绿了才渲染抽帧目检（画面审美仍要目检，探针管不了"看起来对不对"）。
3. 走路段先过 locomotion 数值（step 滑移/支撑脚钉地/轨迹宽度，见 walk-director）
   再看画面。
4. 走路不自然的预防入口：步态风格用 walk-director 的 persona 参数化
   （createLocomotion 参数）与有限落脚验收，不在谱面里手写脚位。

## 参考实现

- 通用探针：`dula-skills/direct-animation-craft/scripts/contact_probe.py`
- 参考 contract：`bio_armor_academy_s1e3/config/contact_contract.json`（14 段全参数化）
- 等效验证：S1E3 薄包装 tools/check_contact.py 与旧硬编码版报告逐字段一致
  （仅 nug_frames 573→663——旧版把无 bento 段的帧静默跳过，新版覆盖 68–71s 卡段）。
