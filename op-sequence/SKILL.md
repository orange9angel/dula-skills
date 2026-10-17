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
