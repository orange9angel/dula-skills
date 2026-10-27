# cel-cinema —— 绘本电影管线（当前一代成片工艺）

**一句话定义**：接近视频大模型观感的成片管线的**统一名称**。3D 渲染只作动作/接触/运镜
底稿，最终画面由文生图原画（场景底图 + 人物 cel + 表情/口型变体）二维合成，粒子特效
保留 3D 层按原时钟合成。用户说"最新的""接近视频大模型效果""3d to 2d 再漫画加工"
均指本管线。

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

- 骨架学 `stardust_clad_s1e2` art_pass（唯一整集交付先例）：镜表驱动、姿势类别复用、
  近景"整肖像当镜头"、jaw 三态接 voice_envs.json 能量包络。
- 纪律学 `cat_leads_cafe_musical/hybrid`：整拍冻结（运动来自换画）、支撑脚锚定、
  相似变换配准（多朝向禁分区 remap）、同图表情变体（禁整脸贴片）、
  渲染实测断言（测像素不测参数，掩码排除字幕带）。
- **场景与人物都要漫画层**：场景底图本身就是文生图整幅原画（含前景/后景拆层做遮挡），
  不是"3D 场景+纹理"；人物 cel 刚性摆放+微参数（lean/compress/breath/hair）。
- 粒子不平涂：萤火/烟尘/魔法光效保留 3D 粒子层（绝对时钟+固定种子），
  发光层 'lighter' 合成、烟普通 alpha（一锅 alpha 会发灰）。
- 口型：短句=能量包络 jaw 三态；**长对白镜头不做贴回 cel 口型**（E04 终局纪律）。
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

镜表时轴无缝 → manifest 显式登记（missingAssets=0）→ probe 断言 →
verify_full_episode（顺序/seek 逐帧一致、音轨 PCM 相同）→ 主代理逐幕审片 →
用户审美批准。参考实现细节：draw-over-animation、build-continuous-story-images、
image-lipsync、cel-look 四个组件 skill。
