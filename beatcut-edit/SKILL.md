---
name: beatcut-edit
description: Produce douyin-style music-driven rhythm-edit videos (卡点/节奏剪辑/广告片) — beat detection, energy-driven effect stack (punch zoom, shake, RGB split, glitch, flash), expression beat-play (blink flutter, reaction cut-ins), velocity ramps, and cel-sequence animated sources. Use for promotional cuts, beat-synced montages, trailer-style edits, cute-pet rhythm videos, or any short video whose edit is driven by the music rather than by a narrative timeline.
---

# Beatcut Edit（音乐卡点剪辑）

## 本地 3D 角色广告（无需生成模型）

用户要求不用生成模型时，复用已注册的 3D 角色、程序动作与库存/程序合成音乐。
参考 `dula-story/episodes/yuki_beat_ad/`：StoryBoard 驱动 12.8s 竖屏 IP 广告，
Canvas 字卡 + ffmpeg 编码。`script.story` 保持唯一镜头时序；字卡按动作名绑定。

- 无对白演出使用 `{Event:Animate|character=Yuki|action=AdPose|duration=...}`。
  当前 Storyboard 只凭 Position/Animation 标签不会实例化角色；不要填假对白。
- 眨眼必须找到模型实际眼组并保存原始缩放。Yuki 现有资产只有瞳孔/眼皮句柄，
  整眼组可从 `leftPupil.parent` / `rightPupil.parent` 获取。
- 卡点动作应区分“离地峰值”和“落地拍点”。用每拍循环完成动作，避免裁掉
  正弦负半周后无意变成两拍一次。末尾停格还需停止场景和表情更新。
- 纯配乐广告的旧 CharacterInspector 可能误报“没有角色”，固定相机名单也可能
  不识别注册插件。保留报告，使用严格 story/scene 检查与实际渲染核实，不声称全绿。
- 竖屏必须单独验构图；横屏 dula-verify 无法证明最终字卡、头发和肢体没有遮挡。
- 音频必须解码最终 AAC 再查浮点峰值。本次程序鼓点的 44.1kHz 单声道 AAC 出现
  单采样越界，降低源峰值仍复现；改为 48kHz 双声道编码后消失。不能只验 WAV。
- 场景工具现使用 `dula-skills/` 工作区布局；历史 `docs/skills/` 探测路径会导致
  找不到项目根目录，已在 scene-designer 的 scene_tool.py 修正。

### 音乐、表情与镜头共用重音（本地 3D 试剪补充）

- 固定 BPM 和每四拍切镜只能证明网格一致。先区分铺垫、短暂停顿和主重音，
  在主重音安排一个明确的表情结果；onset 数量和 RMS 起伏只能辅助初筛，不能
  证明旋律抓耳或已完成听审。
- 眨眼/惊讶/笑脸的**最明显状态**应落在重音，而不只是从重音才开始缓慢变化。
  可提前 2–4 帧闭眼蓄势，在攻击帧切到反应，再留时间让观众读脸。
- 整眼压扁会留下细缝中的虹膜。程序模型可隐藏整眼组并换闭眼弧线，同时联动
  嘴和眉毛；在引擎自动表情更新之后应用确定性演出，避免随机眨眼覆盖卡点。
- 角色转身与画面旋转是两种效果。画面滚转可在重音前短促启动，重音回正并切
  表情；竖屏滚转期间检查头发和四肢，旋转幅度大时调整视野以保持角色完整。
- 检测器的 FFT 窗起点不一定是声音攻击时刻。校正窗偏移或使用短窗包络，并
  记录最终帧率量化后的误差。试剪保留旧输出和独立音乐来源记录。

The edit is driven by the MUSIC, not by a story timeline. Detect the beat grid
and per-onset energy first, then hang the visual grammar on it.

## Workflow

1. **音乐先行**。生成或选定曲子后先做结构化验收（这条直接决定成片上限）：
   - 大模型出曲：火山 Seed-Audio 1.0（接入见
     `../build-character-voice/references/volcano-seedtts.md` 末节）。
     prompt 必须给**曲式结构**（铺底/buildup/drop/break）和清晰的节奏锚点
     （"底鼓每拍清晰"、"有切分和小停顿"），不要写"激烈/动感"这种平词——
     平词出平曲（E04 demo 教训）。俏皮萌宠向参考：马林巴+slap 贝斯+拍掌+
     口哨+摇摆 groove，中速即可，不追求炸。
   - 验收：跑 `beatcut.py` 的 onset 检测看 onset 数（22s 少于一分钟 50 个就换一版）
     和每秒 RMS 能量曲线（要有起伏层次，一条直线 = 单调）。

2. **备素材**（manifest）：
   - `sources`：静帧图（img）和 cel 序列目录（cels，12fps 抽帧的 I2V/OmniHuman
     产物最佳——角色在画面里真的动）混编。
   - `expressions`：反应表情帧（得意/惊讶/灿笑，整帧硬切插入，不走贴回）。
   - `blink_pair`：睁眼/闭眼一对（须用贴回锁定版 cel，框外像素逐像素一致，
     否则半拍交替会整脸抖）。

3. **编排**（一条命令）：
   ```bash
   python scripts/beatcut.py --manifest m.json --track track.wav --out out.mp4 \
     --duration 22 --cut-every 2 --rgb-every 4 --flash-every 8
   ```

## 内置视觉语法（默认开启，参数调密度）

| 语法 | 节奏 | 说明 |
|------|------|------|
| punch zoom | 每拍 | 缩放 1.10→1 指数衰减，幅度跟拍点能量 |
| 微震动 | 每拍 | 抖动幅度跟拍点能量 |
| 硬切 | 每 cut-every 拍 | sources 轮播 |
| RGB 色差 | 每 rgb-every 拍后 0.15s | 边缘彩虹错位 |
| 闪白/故障切片 | 每 flash-every 拍后 0.13s | 两种交替 |
| 眨眼快闪 | 重拍前 1 拍 | blink_pair 半拍交替（萌点核心） |
| 反应帧插入 | 每 flash-every 拍整拍 | expressions 轮播 |
| 变速段 | drop 前后各 2 拍 | 前慢放 0.5×、后倍速 2×（cel 源有效） |
| drop 爆发 | 最强 onset 处 0.1s | 色相脉冲 + 强色差 |
| 镜头滚转回正 | 选定主重音前约 0.4s | 画面转一圈，重音回正接表情；本地 3D 路径先实现于 Yuki V2，非 beatcut.py CLI 通用参数 |

## 验收

- 抽帧看 drop 点是否有爆发（色差/闪光/色相脉冲），重拍插入是否落在拍上。
- 听感：音乐结构验收在第一步做完；剪辑只负责踩点，救不了平的音乐。
- 创意每支片子不同：特效密度用 `--cut-every/--rgb-every/--flash-every` 调，
  语法不够就加——但加新语法先写进本文件这张表。

## 案例：真人广告片《喵星语翻译耳机》（2026-08-30）

首个真人/照片级案例（dula-story/tmp/beatcut_live/）：Seedream 5.0 Pro 出照片级
定妆+产品图（真人+猫+虚构产品，无版权风险）、Seedance 2.0 mini 出 I2V 动作
（真人动作未翻车，¥2.02/4s/720p）、OmniHuman 让照片里的猫开口说话（宠物模式，
1080P）。一支 22s 卡点广告片现金 ≈¥5、全程 <1h。**真人/宠物内容不需要
Seedance 2.5**——2.5（doubao-seedance-2-5-260628）贵 50%，强项是 30s 长视频/
视频编辑，短镜头卡点用不上；只有 2.0 mini 在真人快速动作翻车时再升档。

## 广告片模式（2026-08-30，《喵星语翻译耳机》案例沉淀）

纯轮播卡点 ≠ 广告片。广告片在 manifest 里多四个键（`beatcut.py` 已支持）：

- `windows`：时间窗驱动素材（`t`/`dur`/`type`/`path`），故事节奏优先于拍点轮播
- `voices`：口播配音（`t`/`file`/`text`）——自动混入（音乐 sidechain 闪避）
  并带底部字幕；OmniHuman 生成的对口型视频抽 cel 当 window 素材，口型即表演
- `texts`：文案弹入（`t`/`dur`/`pos`/``big``，PIL 描边字，0.15s 弹入动画）
- `sections`：分段特效密度（开场干净/中段密集/产品段收敛），避免从头闪到尾

案例配方（dula-story/tmp/beatcut_live/manifest_v2.json）：钩子提问 → 女孩口播 →
戴耳机（产品亮灯）→ 猫开口吐槽 → 女孩惊愕 → 产品规格三连弹 → 微笑收尾 tagline。
成本 ≈¥5（Seedream 图 ×3 + I2V ×2），TTS/OmniHuman/Seed-Audio 全在免费额度。

注意：ffmpeg 混音用"VO 先 numpy 预混成 vo_mix.wav 再 sidechaincompress"，不要
在 filter_complex 里堆 adelay+amix 链（实测不稳定）。
