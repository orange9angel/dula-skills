# cel-cinema —— 绘本电影管线（当前一代成片工艺）

**一句话定义**：接近视频大模型观感的成片管线的**统一名称**。3D 渲染只作动作/接触/运镜
底稿，最终画面由文生图原画（场景底图 + 人物 cel + 表情/口型变体）二维合成，粒子特效
保留 3D 层按原时钟合成。用户说"最新的""接近视频大模型效果""3d to 2d 再漫画加工"
均指本管线。

## 开工门禁（2026-10-30 starlight_circus 跳步翻车后设为强制）

生成任何角色原画前，书面逐条回答并留在 episode NOTES，任一条答"否"不得开画：

1. 每个角色是否已有**已验收的身份锚**（全身透明底 + 肖像，spec 逐字写死），且用户已确认？
2. 本批每张原画的 refs 第一位是否为该角色身份锚？是否**一次只画一个角色**（接触镜头除外，且仍以双锚为首 ref）？
3. 姿势参考来自哪里（3D 底稿帧 / 已验收姿势画）？未经验收的 3D 底稿不得开画。
4. 近景/中近景是否**直接用肖像锚做局部编辑**（嘴/眼/表情），而不是重新生成一张脸？
5. 比例门（地标表 + `check_cel_proportions.py`）与原生分辨率脸部对比是否在入片前执行？
6. 合成是否走共享运行时（cel-stage / raster-face / cel-integration），而不是单集自写合成器？

反例：starlight_circus pilot8（2026-10-30）六条全部跳过——以群像画 300px 裁区当身份参考、双人宫格、
文字描述姿势、近景另画新脸、自写 Python 合成器。结果三个镜头的诺娅像三个演员；画数是基线 3 倍
仍被判不流畅（每次换画都换一张略不同的脸=闪）。加载 skill 不等于执行 skill。

## 与上一代的分工（不要选错）

| 管线 | 画面主体 | 适用 |
|---|---|---|
| **cel-cinema（本管线，当前一代）** | 文生图原画二维合成，场景与人物都有漫画层 | 正式成片、童话/绘本/艺术化要求 |
| hybrid-craft-scene（上一代） | 程序化 3D 直出 + 文生图纹理/背景板皮肤 | 试片、预演、动作/接触验证底稿——**同时也是本管线的底稿来源** |
| previz-animatic | 平面零成本预演 | 剧本节奏验证 |

纪律：cel-cinema 立项时先用 craft3d/viewer 链做 3D 底稿（动作、接触、运镜、时长、音频
全部先锁），再进本管线二维化。**不要在 3D 底稿未验收前开始生成原画**。

## 数据流

```
3D viewer 链成片（底稿，sha256 锁定）
  → pipeline.mjs --step prepare / bake        # 逐帧关节+相机(透视)+接触+粒子锚点
  → 文生图资产（身份锚 → 场景底图 → 姿势 cel → 相位画 → 表情/嘴/眼变体）
  → art_pass 页（cel-stage 刚性摆放 + raster-face 口型表情 + 接触影
      + 粒子 3D 层重宿主合成 + 字幕）
  → pipeline.mjs render / probe / package + verify_full_episode.py
```

执行入口：`dula-skills/draw-over-animation/scripts/pipeline.mjs`（五步骤）、
`verify_full_episode.py`（顺序/seek 逐帧一致+音轨 PCM 比对）；
runtime 模块在 `dula-skills/draw-over-animation/assets/`（cel-stage/raster-face/
baked-cel-clip/particle-stage/story-state 等，prepare 步骤自动同步）。

## 文生图通道纪律（2026-11 更新）

- **整帧生成**：codex CLI（订阅配额，零边际成本，串行前台跑）优先；火山 Seedream
  付费通道余额充足时可用（`dula-story/.env.ark`）。
- **透明底人物 cel 可直接 prompt 产出**：gpt-image 经 codex 支持真 alpha——
  "FULLY TRANSPARENT background (real PNG alpha), no backdrop/ground/shadow" +
  1024x1536 即得可用 cel（borrowed_moonlight A2，16 张全一次通过）。
- **编辑类变体（嘴/眼/表情局部改）只能 codex**——qwen/wanx/seedream 贴回全部判死
  （cat_leads E02–E04 教训），配额耗尽就等，不许 fallback。
- **火山欠费时的标准配置：codex 文生图（画面）+ Suno 网页驱动（音乐/歌曲，走
  suno-driver skill）+ 既有已生成音频资产复用**。seed-tts/Seed-Audio 恢复付费后再用。
- 角色一致性：身份锚 + 最近已验收帧双 ref；拒收的图永不当 ref；比例锁逐字写进 prompt；
  跨画比例门 = 人工地标表 + check_cel_proportions.py 驳回。

## 画面纪律（两条参考路线的翻车沉淀，细则见各自 skill）

- 骨架参考 `stardust_clad_s1e2` art_pass：镜表驱动、姿势类别复用、
  近景"整肖像当镜头"、jaw 三态接 voice_envs.json 能量包络。
- 纪律学 `cat_leads_cafe_musical/hybrid`：整拍冻结（运动来自换画）、支撑脚锚定、
  相似变换配准（多朝向禁分区 remap）、同图表情变体（禁整脸贴片）、
  渲染实测断言（测像素不测参数，掩码排除字幕带）。
- **场景与人物都要漫画层**：场景底图本身就是文生图整幅原画（含前景/后景拆层做遮挡），
  不是"3D 场景+纹理"；人物 cel 刚性摆放+微参数（lean/compress/breath/hair）。
- 粒子不平涂：萤火/烟尘/魔法光效保留 3D 粒子层（绝对时钟+固定种子），
  发光层 'lighter' 合成、烟普通 alpha（一锅 alpha 会发灰）。
- 口型：短句=能量包络 jaw 三态；**长对白镜头不做贴回 cel 口型**（E04 终局纪律）。
- **唱段口型必须由歌声算出**（星辰马戏团 R4）：手排时间表和原画画死的张嘴都会被用户看出「嘴和声音不匹配」。
  用 audio-perception-review 的 `align_sung_lyrics.py`（DTW + 声学地标）驱动 dialogue-face-track，
  并用 `check_av_sync.py` 对账实际显示的嘴、换画落拍与运动/音乐协调；数值改善不等于审美通过。
- 既有有限动画的返修必须覆盖实际可见对白的全部选画路径，不能只把肖像特写接到
  jaw 就声称全片口型完成。R3 中景漏接与矩形贴片的原因、修法见
  [同图五官遮罩与对白覆盖](../draw-over-animation/references/feature-islands-and-dialogue-coverage.md)。
- **不用视频模型的连续动作 =「姿势阶梯」**（crystal_aria 尾奏，用户目标「文生图加我们的 skill 做到动作平滑」）：三张姿势溶接被判「不连贯」。
  codex 逐张画中间画，refs 依次为身份锚、上一张已验收帧、目标姿势，提示词写明本张走到动作的百分比；曝光按缓动分配（大步 5 帧、
  近终点 3 帧），不做跨张形变；全部 cel 用同一比例（逐张按身高缩放会一胀一缩）。
  codex 生成的进度常前重后轻（前两张步子大），曝光据实际间距调，而不是按计划百分比。
  **配准按不动的部位**（v3→v4 返工：补到一拍二后用户反馈「帧多了反而抖」）：站着的人按裙摆/脚的相位相关链式配准钉死，
  不能按头——每张画头身相对位置不同，钉头会让整身随换画左右跳，画越密越抖；一拍二不要加 50% 溶接帧（三分之一帧成双影）。
- 已否决反模式：整图平移冒充动画、网格扭曲换腿、跨图移植窗口、整脸贴片、
  降采样拼图过脸。
- **位置、比例和接触必须在最终绘画中同时成立**（borrowed_moonlight R3）：R2 的
  脚底地面线修正仍留下巨人走向门、老人站桌面、登阶错位。独立绘制底图应以绘画
  支撑面、门高、台阶和遮挡重新标定场面，使用一套底图坐标相机；不能仅凭 bake
  锚或 +/-140px 修正通过。星阶同样需要核对实际画出的阶面，不自动豁免。
  执行件与验收见[绘画空间与最终接触时钟](../draw-over-animation/references/painted-space.md)。
- **环境辉光锚点分空间**：天体/道具灯（月、油灯、门缝）用世界锚投影（跟镜头）；
  房屋窗灯等"画在底图上"的内容必须底图空间锚定——3D 世界窗位与底图房屋位置
  不一致，世界锚投影会悬空成浮空光斑。
- **共享模块 clamp 陷阱会复发**：cel-stage 的 clamp 是单参 [0,1]，三参调用静默吞掉
  修正量（R2 在 A3 已记录的情况下仍复发三处，其中采样器坐标钳把"站位区采样"变成
  左上角天空色，tint 错色而不自知）。凡"修正了但只差一点"的回归，先怀疑修正量被吞。

## 验收门禁

重复渲染同一时刻一致不等于连续播放稳定；嘴眼裁区通过也不覆盖人物整体波动或画面
抖动。此类反馈需独立记录、以连续画面核查，见
[R5稳定性漏检](../character-attention-review/references/miss-learning.md#局部嘴眼通过不代表连续画面稳定borrowed_moonlight-r5)。
用户接受但明确暂不修改的问题标为保留项，记录成片摘要，不当成已修复或自动启动新一轮。

镜表时轴无缝 → manifest 显式登记（missingAssets=0）→ probe 断言 →
verify_full_episode（顺序/seek 逐帧一致、音轨 PCM 相同）→ 主代理逐幕审片 →
用户审美批准。参考实现细节：draw-over-animation、build-continuous-story-images、
image-lipsync、cel-look 四个组件 skill。

## 大体量数据与Git归档

保留原画、声音源与溯源、配置、制作入口、精选审片图及摘要；可重建的整轨混音、
逐帧导出和成片按仓库规则留在本地。动作烘焙JSON也可能很大，不能仅凭扩展名当作
普通小文本：borrowed_moonlight历史`motion_full.json`达112.47 MiB，需显式LFS管理。
推送前检查整个未推送提交范围的大对象及LFS总量，不能只统计当前提交。本例R5新增
约104 MB，但积压历史的LFS上传达3.2 GB；这不是单集成片大小。超限历史修复应保留
原提交备份、隔离脏工作区，只迁移未发布范围，并核对内容摘要及普通快进推送条件。
