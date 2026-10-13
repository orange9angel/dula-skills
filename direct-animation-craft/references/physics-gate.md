# 编写期物理门禁（physics gate）

物理错误（穿模、悬浮、空手托盘、超臂长目标）不该活到渲染后由用户复看发现。
本门禁把它前置到写谱面阶段：探针当编译器用，不过不渲染。工艺沉淀自
bio_armor_academy_s1e3（《9章》S1E3，P10 十四段断言全绿后用户零物理类反馈；
P12 扩 gait/limb_attach/worn_prop；P13 扩 grip/palm_semantic；P14 扩
hand_body_mesh/rest_support/state_consistency 共 22 段——但 P13 同时证明断言
全绿≠看起来对，需按末尾协议处理数值未覆盖的交互）。

减少视觉检查或升级碰撞算法时先读 [算法防穿模与低成本验收](collision-prevention.md)。
以正反例、几何/时间覆盖和版本一致性决定数值结论的范围；当前工具绿灯不自动
代表完整物理保证。已覆盖的几何回归无需每轮重复多机位审片。

## 三层防线

1. **生理域常量表 + 可达性**：写 IK 目标点之前先过可达性——肘腕目标必须在臂长
   球壳内（够不着就报错，不要静默 clamp：S1E3 实录"扶盒沿点"超臂长被 clamp 后
   手悬空；坐姿肩高 1.16m/台面 0.58m/臂长 0.43m 时，身侧台面必须带 lean 俯身才够得着）。
   常量表：腕扭转 ±60°、掌法向量⊥前臂轴、手-躯干轴距离域、步幅/落脚域
   （数值见 [contact-and-hands.md](contact-and-hands.md) 与
   [walk-director](../../walk-director/SKILL.md) 的已验收实测）。
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
| `locomotion[actor]` | `{kind,root,yaw,bob,step,steps,feet,legs}`（行走段逐帧） | gait |
| `contact.arms` / `contact.torsoAxis` | 手臂三点（肩/肘/腕，mesh 局部→世界）+ 躯干轴两点（含 bob/lean） | limb_attach |
| `worn` | 穿戴件盒 vs 穿戴者网格（负 margin=深穿才报；穿戴件自身打 `userData.probeExclude` 跳过） | worn_prop |
| `contact.grip` | 托盘接触：盒底投影内顶点-底面 min\|y\|（touchMin）+ 指节-盒体最近距离 | grip |
| `contact.palmIn` | 送嘴掌向：掌心·（手→躯干）点积（约束激活帧才记录） | palm_semantic |
| `handBody` | 手 skinned mesh vs 躯干/大腿代理盒（负 margin 深穿才报，代理盒 92% 半径+骨盆侧翼延伸） | hand_body_mesh |
| `contact.handRest` | 掌点→大腿轴/盒 OBB 距离（support=取小） | rest_support |
| `contact.doorOpen`/`doorPos`/`lidOpen`/`windGust` | 有状态元素的归一化开度/位置/环境触发量 | state_consistency |
| `locomotion[].feet[].pitch` | 足踝俯仰（负=背屈足尖抬；支撑期滚动输出） | foot_roll |
| `limbBody` | 臂轴采样相对躯干椭圆环列的径向近似 g（未计管半径，不是精确表面净空；袖根内埋区已滤） | limb_body_mesh |
| `limbBody[].rootG/reach` | 袖根邻域 g（仅记录不判，判别力证伪）/ 腕-肩距÷臂长 | limb_body_mesh / reach |
| `cloth` | 襟片面片局部系穿透检测（臂管段端点法向换号+交点落襟片范围） | cloth_body |
| `surface.pairs` | 部件对的实际顶点/有限衣片代理侵入深度、最坏点、评估数、过滤数与方法标识 | surface_clearance（P22 新增，旧探针同时保留） |

新段执行顺序追加在 SECTION_ORDER 末尾（gait/limb_attach/worn_prop 在 continuity 之后）——
插中间会改变 failures 帧内段序，破坏跨版本报告可比性。

穿戴件纪律（S1E3 P12 实录）：挂在髋部的硬盒道具（书包）若按"几何贴合"摆放必然与
大腿面常交——正解是**枢轴移到包顶 + 外移 + 重力外倾角**（挂点扫描一次渲染定 offset：
逐候选改变换→探针→还原，纯函数不进画面），再用负 margin 断言"只报深穿、放行贴触"。
抬臂过肩线会让袖根脱出躯干肩环覆盖（挥手肩部断缝实录）——limb_attach 的仰角上限
即"手不过肩线"的数值化（轰刚挥手顶点 1.58→1.46，上臂仰角 max 72.6°→域 85°）。

probe 查询串约定：`render.mjs --q "&probe-door=1&probe-bento=1"`；探针模块惰性
import（不进正片渲染路径）。15Hz 姿势帧（一拍二）下的道具连续性按姿势帧比较，
别按输出帧（S1E3 实录：输出帧级位移会误报一拍二的正常走步）。

## 工作流门禁

S1E3 已支持 `episode_gate.py <episode> --physics-only`：纯数值采样、数值 seek、
接触/步态/声画检查，跳过审片图与成片像素检查；详细边界见
[collision-prevention.md](collision-prevention.md#p22-已实现的数值检查入口)。
`--skip-render` 可复用未过期 trace；surface_clearance 要求的源码/资产/config
指纹变化或窗口采样缺失会失败，不能复用旧绿灯。

1. 写谱面 → `contact_probe.py`（contract 先行）红 → 改谱面/道具路径 → 绿。
2. 报绿后核对覆盖与输入版本；只为未覆盖交互、异常或画面审美生成必要抽帧。
3. 走路段先过 locomotion 数值（step 滑移/支撑脚钉地/轨迹宽度，见 walk-director）
   再看画面。
4. 走路不自然的预防入口：步态风格用 walk-director 的 persona 参数化
   （createLocomotion 参数）与有限落脚验收，不在谱面里手写脚位。
5. **渲染稳定性终审**（C8）：出成片后跑 `flicker_probe.py`（成片逐帧二阶差分，
   watch 区回归带+背景角格粗扫+**台阶检测**——声明 `step_ratio` 的区域相邻帧
   边缘密度比超阈即红，专抓换层/换密度这类二阶差分抓不到的一次性阶跃，P20 铁丝网
   换层 pop 实录）；episode 侧 `config/flicker_watch.json` 声明
   共面件/细 alpha 件风险区）；已接入 `episode_gate.py` 第七步
   （成片比源码旧自动跳过并标注，提醒先 `--out`）。

## 参考实现

- 通用探针：`dula-skills/direct-animation-craft/scripts/contact_probe.py`
- 参考 contract：`bio_armor_academy_s1e3/config/contact_contract.json`（段数以当前配置为准）
- 等效验证：S1E3 薄包装 tools/check_contact.py 与旧硬编码版报告逐字段一致
  （仅 nug_frames 573→663——旧版把无 bento 段的帧静默跳过，新版覆盖 68–71s 卡段）。

## 逐拍近景审片协议（P13 实录：断言全绿≠看起来对）

数值探针是编译器，但"盒浮在掌上 5cm"这种错误可以一路绿灯（距离阈值内的悬浮）。
新交互或数值尚未覆盖的接触，可出 2–3 机位近景帧（特写+侧写各一），过五点清单。
已由经反例验证且覆盖完整的数值门禁承担的几何项目，无需每轮重复看图；
只要求算法诊断时明确覆盖缺口，不把视觉审片扩成额外任务。

1. **掌向**：送嘴=掌心向内（不是向外反掌）；挥手=掌心朝外；托举=掌面朝上。
2. **接触**：盒底贴掌面（无缝）；手指扣在盒底前缘/侧壁；放置帧手贴盒。
3. **支撑**：每个可见盒/道具都有支撑者（手/台面/摞在下层盒上）。
4. **连接**：穿戴件的带/绳两端都连得上；签的两端=捏合区与食物。
5. **穿戴件**：包/带/扣不穿腿不穿躯干，摆动跟得上身体。

工具：`render.mjs --check --shots config/review_shots.json --board <dir>`——
shots JSON 逐镜点名 `[{name,t,camera:[px,py,pz,lx,ly,lz,fov?]}]`，不走 checkTimes，
4s 出 22 帧（S1E3 P13 基建）。审片发现的任何问题顺手修掉再复跑探针。
抽样审片的教训（P13 一轮四例）：掌心语义错误、俯身肩缝、托盘浮盒、递签指向，
全部是当时 17 段断言全绿时近景才暴露的；应将可数值化的掌向/贴合要求补入
探针，未覆盖的读感再用审片判断，不把所有接触语义永久交给视觉。

## 穿戴件做工纪律（P13 实录）

- 包类=**背带+包体+包盖三件套**，两端都要连得上（背带尾→包顶挂点用连接件桥接，
  随包摆动）；只有一条绳不算完成。提亮包体色别撞裤子色（深棕撞深蓝远景读不出）。
- 挂点净空用**扫描定稿**：一次渲染里逐候选改挂点变换→探针→还原（纯函数不进画面），
  选中零命中且留 ≥2cm 余量的最小偏移；别逐候选整渲染瞎试。
- 坐姿大腿外侧鼓出比站姿宽 ~4cm：站姿净空的挂点，坐下可能复穿——扫描窗口必须
  覆盖坐姿段；前摆到腿前侧的方案在探针下不成立（实测复穿），可读性靠配色/连接件。
- 次级摆动沿用挂载件机制（枢轴移到包顶：重力外倾角+风摆+逆 lean 回摆），包盖挂成
  包体子件随摆。
