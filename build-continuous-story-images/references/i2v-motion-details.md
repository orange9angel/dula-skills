# I2V 次级动态细节词表（i2v-motion-details）

> 适用：Seedance / 任何 image-to-video 模型的动作 prompt。
> 定位：**正面**指导"怎么让布料、发丝、环境自然地动"，与
> `walk-director/references/keyframe-walk-shots.md` 的"A/B cel 锁死纪律"
> 互补——cel 换帧仍锁死，I2V 连续段则必须主动写出次级动态。
> 首用：cat_leads_e05_morning_sketch（2026-08-31）。

## 核心原则

1. **一镜一个主风向**。同一镜头内所有次级动态（裙、发、草、尾）必须同向，
   写明方向（"from the LEFT" / "from behind the camera"），禁止只写 "wind"。
2. **动幅度分级，不动轮廓主体**。次级动态只许动"末端"（发梢、裙摆、草叶尖、
   尾尖），发根/肩线/躯干轮廓必须稳定，否则 I2V 会整体漂移。
3. **动词具体到材质**。不写 "clothes move"，写清什么材质怎么动（见下表）。
4. **镜头运动单独写死**。次级动态与运镜分两行写：运镜行用
   "The camera is completely fixed" 或明确 dolly/pan；动态行只管画面内的动。

## 风力分级（与叙事绑定，不是越大越好）

| 级别 | 名称 | 叙事场景 | 可见表现 |
|------|------|----------|----------|
| L0 | 无风 | 室内、紧张对峙、特写情绪 | 只有重力垂坠；布料完全静止 |
| L1 | 微风 | 清晨、傍晚、治愈系日常 | 发梢 2-5cm 摆动；裙摆边缘涟漪；草叶尖颤 |
| L2 | 和风 | 行走户外、情绪转亮 | 裙摆明显起落；长发成束飘动；草浪成片 |
| L3 | 阵风 | 转折、惊喜、抒情高点 | 裙摆压向一侧；头发遮面级别；只用于单点强调 |

**纪律**：静态情绪镜头（对视、沉思）用 L0-L1；L3 一集最多一处。

## 材质动词库（英文 prompt 用）

### 衣物
- 百褶裙（cotton pleated skirt）：`the pleats ripple gently from the hem` /
  `the skirt hem lifts and settles softly`（L1-L2）
- 衬衫/袖口：`the shirt sleeves flutter lightly at the cuffs`
- 长裤：`the trouser legs sway faintly at the ankles`（L2 以下只动裤脚）

### 头发
- 长直发：`the tips of her long hair sway and lag slightly behind her head
  movement`（跟随延迟 ≈0.3s，这是"头发有重量感"的关键写法）
- 短发/刘海：`his fringe trembles slightly at the tips`（L1；短发只动梢）

### 动物
- 猫尾：`the tail sways gently with a slow S-curve, the tip leading the motion`
- 猫毛：`the fur at the tail base and cheeks ruffles faintly`（L2 以上才写）

### 环境
- 草：`the grass tips tremble in a slow wave from LEFT to RIGHT with a slight
  phase offset between tufts`（相位差是"自然感"关键，防整齐划一的假感）
- 树叶：`the leaf clusters shiver lightly, a few leaves detach and drift down`
  （落叶仅在 L2+）
- 水面：`the water surface carries slow flat ripples drifting downstream`

## 禁止项（翻车预防）

- 禁止 `wind blowing everything` / `dynamic scene` 这类全画面激励词——会触发
  轮廓漂移和背景形变。
- 禁止让布料穿过身体：写 `the skirt moves around her legs without overlapping
  them` 可预防裙摆穿腿。
- 布料动但**人数、肢体数、构图不变**：每条动态 prompt 结尾带
  `Character count, poses and framing stay exactly as in the first frame.`
- 逆光/夜景中 L1 动态几乎不可见，别浪费钱——把动态镜头安排在受光场景。

## 验收（抽帧）

1. 从 I2V 成品均匀抽 6 帧叠放：轮廓主体（头/躯干/四肢位置）偏移 ≤ 2%。
2. 布料/发丝/草在帧间有可见但连续的运动（无跳变、无瞬移）。
3. 布料不穿腿、不遮脸；头发不遮眼（除非叙事要求）。
4. 风向在镜头内一致；与相邻静态 cel 的风向不冲突。

## I2V 语法边界（2026-09-05 导演看片后定，优先级高于上面的词表）

E05 导演复片结论：静态抽帧全部达标，但**连起来看布料/发丝仍有"橡胶布条"
形变感**。根因是能力边界：平涂色块没有纹理锚点，视频模型预测布料运动只能
整体形变——prompt 词表能管"动不动、动多少"，管不了"动得像不像布料"。
因此立下选型纪律：

**I2V 只用于三类镜头**：
1. 全身位移：走路/跑步横移（角色在画面中整体移动，如 E05 猫带路、过桥）；
2. 运镜镜头：push/pull/pan 等镜头运动为主、主体小动作；
3. 大环境运动：水面、云、烟、草浪这种没有明确轮廓主体的运动。

**以下回到关键帧语法（画姿势变体做 A/B 交替或中间帧），不要用 I2V**：
- 布料/发丝的特写级飘动（裙摆、头发是视觉焦点时）；
- 面部表情变化、情绪转折（OmniHuman 之外的镜头）；
- 任何"观众会盯着看形变对不对"的镜头。

**程序化图层的边界**：只画点状/抽象元素（萤火、露珠、蒸汽）。
有具体形状的生物/物体（鸟、落叶、蝴蝶）画进关键帧或不画——E05 的
程序化飞鸟在平涂画面上精度不匹配，近看露假。**半透明椭圆/色块叠层
（如 dappleSway 光斑）也禁用**：E03 和 E06 两次实测半透明椭圆在平涂
画面上显假（"visibly fake ellipses"），光斑/树影一律烘焙进关键帧。
**cloudDrift 椭圆云也受限（E07 实测）**：叠在已烘焙绘画感云层上像贴纸。
程序化云只允许出现在**纯平涂空天空**的画面；有烘焙云就不用，云层运动
走 A/B 变体语法。

## 附：E05 实测段（2026-09-05，cat_leads_e05_morning_sketch）

- 模型：满血版 doubao-seedance-2-0-260128 @1080p，4s 取前段抽 12fps cel。
- 静态验收全过：发梢滞后摆动、裙摆下摆涟漪、草叶相位差可见，轮廓零漂移。
- **动态复片不过**（导演看片）：布料运动呈布条形变感 → 促成本文「语法边界」
  一节。词表仍有效（它让运动"有且方向对"），但不能把 I2V 用在布料特写镜头上。

**A/B 双帧交替的频闪问题（E07 V1 导演复片）**：两帧交替超过 ~0.5s 周期会
读作"闪烁"而非"摇摆"。修法是加中间帧变三帧循环 A-mid-B-mid（codex 双图
编辑 prompt："halfway between image 1 and image 2"，E07 柳枝实测通过）。
周期 ≤0.3s 的快速微动（猫耳）双帧可接受；≥0.5s 的环境摇摆必须三帧。
