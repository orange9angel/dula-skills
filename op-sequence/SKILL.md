---
name: op-sequence
description: 动画片头（OP）制作全链路工艺——歌先行双通道抽卡（Suno 会员优先/volc-song-gen 兜底）、拍网锁定五段式蒙太奇、群像亮相与战壳生长秀语法、画外音 gag 收尾、验收清单。参考实现 stardust_clad_op（49.2s OP）。
---

# OP Sequence（动画片头工艺）

参考实现：`dula-story/episodes/stardust_clad_op/`（《星屑战壳》OP，49.2s，
craft3d viewer 链 + 文生图混合场景 + Suno 主题歌）。

## 总原则：歌先行，画面跟着拍网走

OP 是音乐驱动的蒙太奇，**先定歌再排画面**。正片链路（剧本→配音→重排）在这里
不适用——OP 的"剧本"就是拍网。

## 第一步：主题歌双通道抽卡

| 通道 | 何时用 | 成本 | 说明 |
|------|--------|------|------|
| **Suno（WebBridge 走用户已登录浏览器）** | 默认首选（用户有会员时边际成本为零） | 0 | 质量上限高，复古热血摇滚等风格还原好；流程见 suno-driver 2026-10-17 节（Create 提交→More options→Download→WAV→Unlock & Download；歌词框用 CDP insertText） |
| **volc-song-gen v4.3** | 全自动兜底/批量抽卡 | 0.002 元/秒 | 风格控制弱（Epic 配置也可能产出慢版），BPM 必须逐首实测 |

抽卡纪律：
- Suno 一次 Create 出 2 个 clip，**两个都下载**（可能一个有完整人声、一个只有
  尾段唱词——实测 B 版 41s 里只有 30s 后有人声）。
- **人声验收**：whisper 必须 `no_speech_threshold≤0.2 + condition_on_previous_text=False`，
  默认阈值会把歌声整轨拒识成零段落（suno-driver 已记录）。零段落 ≠ 纯器乐。
- **选版**：客观评分（score_v18.py 模式：arc_contrast/build_slope/drop_impact/
  rhythm_clarity）+ BPM 实测（热血 OP 要 150+）+ 人声覆盖区间。听感终审归监制。
- 溯源：逐文件 `.source.json`（song id/clip id/sha256/时长/style 全文）。

## 第二步：拍网 + 唱段结构

```bash
# librosa beat_track → beats[]/downbeats[]（downbeat 相位用 onset 强度 4 相位取最大）
# faster-whisper（宽松参数）→ whisper_lines[]（唱段时间戳，确定主歌/副歌/器乐尾结构）
```
落盘 `config/beatgrid.json`。timeline 条目边界全部吸附 beats[]，断言偏差 <20ms；
动作顶点（接触帧、生长起点、定格）压 downbeat。

## 第三步：五段式 OP 结构（49s/152BPM 实例）

| 段 | 时长 | 内容 | 声音 |
|----|------|------|------|
| intro | 2 小节 | 黑场淡入全景 + 标题字卡淡入 + 缓推 | 歌声直接入 |
| verse1 | 主歌一 | 主角团逐个登场秀装备（每人 ~2.5 小节：走入→换脚转身→铠甲分段生长） | 生长起点压 downbeat + energy_charge SFX |
| verse1' | 主歌二 | 打斗快切蒙太奇（1~2 拍一切，格挡/冲刺/对拳/击飞） | 接触帧压 downbeat，打击 SFX+白闪+拟声词大字 |
| verse2 | 尾段 | 低机位冲锋 → 合体 gag → 全员定格 pose |  gag 顶点压关键唱句入点 |
| outro | 器乐尾 | 定格+标题再现 → 画外音 gag → 拟声收尾 → 淡黑 | 画外音 duck −8dB |

要点：
- **收尾 gag 放器乐尾**：唱段结束后（如 44.2s 后）留一句角色画外音（例：女神
  慵懒一句"打完记得把锅刷了。"），史诗余韵里抖包袱，是搞笑番 OP 的签名拍。
- 画外音配音走火山 seed-tts（volc-voice-casting 选声）；speech_rate 与时长
  非单调，卡窗用静默裁切后按实际时长 QC，别信 rate 参数。
- 特效件全部纯 (t,state)（冲击环锚真实接触点、LCG 火花、白闪 ≤.55、拟声词
  大字、地裂缝），抄 s1e2 viewer.js 内联模式，不要用 dula-assets 的
  AnimationBase FX 类（引擎链范式，无世界锚点）。
- 铠甲生长秀语法：setCladState(cladT) 分段 scale 蔓延（clamp(t*N-i*.8)）+
  生长前锋环 + 加色 emissive 接缝行波（波谷保底亮度 ≥.5，否则群像远景读不出）。
- 挂肢体的盘/盾面朝向按 rig 轴推导，特写机位跟着盘面法线走，别让角色转体迁就。

## 第四步：场景质感

纯程序场景先钉构图/机位/谱面，**混合纹理升级放最后**（hybrid-craft-scene：
Seedream 纹理+法线派生+背景板/连续天空，几何动画不动只换皮肤）。连续天空
积木已晋升 `dula-assets/lib/craft3d/continuous-backdrop.js`。

## 验收清单

1. `render.mjs --check` 全绿 + seek 像素容差校验
2. `episode_gate.py` 全绿（contact 断言按 physical-completeness 矩阵；
   无交互拍声明不适用理由）
3. 成片 ffprobe：时长=歌长、h264+aac、AAC 峰值 < −1.8dBFS
4. 抽帧复查：每个 downbeat 接触帧、定格 pose、画外音字幕帧、淡黑帧
5. **正常速度人眼视听终审**（歌画同步的体感只有这一条算数）

## 与相关 skill 的分工

- 歌：suno-driver / volc-song-gen（本 skill 只管选版与拍网）
- 口型：OP 一般不对口型；角色唱歌镜头走 song-lipsync
- 场景纹理：hybrid-craft-scene；字卡：title-card；ED：credits-sequence
- 正片预告剪辑（有正片后）：promo-cut

## 音频通道偏好（监制 2026-10-17 明确）

- **配乐**：Suno 会员通道优先（边际成本零+风格上限高），volc-song-gen 全自动兜底
- **配音/音效/环境音**：全走火山（seed-tts-2.0 + Seed-Audio）。**不要**用
  fighting-sfx 程序合成当正式音效（只能打样）——《星屑战壳》R2 因此整轮返工。
- Seed-Audio 批量：逐支 prompt+`.source.json` 溯源+skip-if-exists（参考
  stardust_clad_op `tools/gen_sfx.py`）；环境底床做三道节律验收，连续性检查
  要单轨验（别量混音，歌曲尾奏回落会误判 dropout）。
- **AAC 编码过冲**：混音 wav 卡 −1.8dBFS 不够，上限 −2.2dBFS 留编码余量。

## R2-R2.6 实战补充（《星屑战壳》）

- **多场景跳切**：OP 要跨场景（登场分场景→打斗跨场景硬切→冲锋一场一镜汇聚）。
  多场景同存按段切 visible（硬切压拍，禁止渐隐穿帮）；timeline 每段带 scene 字段。
- **穿戴件**：悬浮环是雷区（"腰上圆圈挂铁片"被监制点名），贴身纪律和
  clad_fit 探针见 character-modeler。
- **出拳接缝**：目标点 ≤.85 臂长 + 出拳拍 `noSwing`（跑步摆臂叠加会顶爆
  reach 钳位）+ 三角肌盖遮断面；新角色先量臂长再摆道具目标点。
- **肖像/审片帧要 solo 隔离**（render --shots 加 per-shot 隐藏其他角色），
  否则其他角色按谱面姿势乱入镜头（悬浮腿事故）。
- **画外音 gag 可升级为真人出镜**：女神坐圣物上晃腿说台词比纯画外音效果好；
  口型用能量包络轨即可（OP 不需要逐字视素）。
- **接手被叫停的并行轮先 `git status` 盘点半成品**：评估可用性后合并，
  比推翻重做省一整轮。
- **封面帧纪律**：第 0 帧必须是可读构图帧。"从纯黑淡入"等于把视频封面/平台
  抓帧让给全黑——淡入保留，起点亮度不能是 0%（夜景基调 25~35% 起）。验收时
  抽成片第 0 帧确认（ffmpeg select=eq(n\,0)）。

## R11 必杀技与喊招工艺（2026-10-18《星屑战壳》R11，OP+S1E1 双集实测）

- **喊招压拍**：蓄力期起喊、末字压接触帧——seed-tts 实测时长首尾静默裁切（-45dB）
  后回推摆点（rate 非单调，别靠 rate 卡窗）；喊招增益顶格（1.6）并 duck 歌曲
  （与台词 duck 窗合并后统一施加，别分两次乘）。喊招 QC 同台词拼音口径。
- **技名卡**：canvas overlay（刷痕底条斜切+楷体大字+色边外发光），纯 t 驱动
  （0.14 弹入-停留-0.2 淡出，0.85-0.95s）；双人同喊用 left/right 半屏分卡。
  卡不进场景几何，不与字幕层抢位（字幕在底部，卡在上三分）。
- **必杀 VFX 纪律**：AdditiveBlending + LCG 种子 + 纯 (t,t0,anchor)；锚点=真实接触点
  或活锚点帧帧活取（渲染层纯函数，pose 计算不读网格）；特效不糊接触帧本身——
  弹雨/残影的密度窗避开接触瞬判读区，白闪仍 ≤.12s。亮场景（晨景）加色件 opacity
  按首帧目检抬一档。
- 资产形态：技定义+VFX 构建器+技名卡 = 可复用积木，落 dula-assets 角色包
  （stardust/moves.js），剧集侧只摆点。
