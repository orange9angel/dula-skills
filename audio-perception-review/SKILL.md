---
name: audio-perception-review
description: 用算法「听」片：配音/唱段、配乐、环境床、拟音、总混音的分层可测指标，以及声画同步与协调探测——唱句逐字对齐（DTW + 声学地标）、实际显示口型对账、换画落拍（Beat Align Score）、画面运动与音乐起音互相关、Audiobox 审美代理分。用于口型不跟声、跳舞不卡拍、声音层互相遮蔽、环境床循环感、混音回归检查，或任何需要主代理自己判断音频与画面是否配合的场合。
---

# 音频感知审查（算法听审）

主代理听不到声音，也不能按正常速度看片。本 skill 把「听」拆成可测量的维度，
用于**发现问题和卡回归门**；它不给审美结论——"好不好听、有没有感染力"
仍以正常速度人耳听审为准，报告里要写明哪些结论来自指标、哪些需要实听。

## 选哪种"耳朵"

| 问题 | 有效表征 | 无效/误导 |
|---|---|---|
| 唱的是哪个字、何时起 | 音高曲线（pyin，唱歌一字一音符）、4.5k+ 擦音爆发、低频能量回升/凹谷 | MFCC（压掉音高）；ASR 词时间戳（与 DTW 同模型同偏差，不是独立证据） |
| 节拍/卡点 | 全曲 beat grid（beat_track 一次算完存盘） | 短窗口重测速度（8s 窗口实测 108/215 BPM，全曲 146.5） |
| 人声是否被盖 | 1–4kHz 语音带的人声/配乐能量比（SMR），按人声有声帧 | 总响度对比 |
| 环境床循环/起伏感 | 1s RMS max/mean、50ms 包络 0.5–1s 自相关、4–8kHz 嘶声占比 | 主观"听起来还行" |
| 整体"质感"回归 | Audiobox Aesthetics（CE/CU/PC/PQ，1–10） | 把分数当作品评分 |

## 脚本

全部只读、确定性，产 JSON。依赖 `dula-story/.venv`（librosa、faster-whisper 本地模型、torch）。

### 1. `scripts/align_sung_lyrics.py` —— 唱句逐字对齐

```
python align_sung_lyrics.py --stem 最终放置人声分轨.wav --lines lines.json --out alignment.json [--character noya]
```

最终放置的**分离/分轨人声**（不能用混音总线）→ 已知文本 Whisper DTW → 声学地标单调 DP 吸附。
输出 clips（含逐段能量、gate、chars 声韵母、breaths）可直接喂
`draw-over-animation/assets/dialogue-face-track.js`（`inhaleLead` 选项对唱段显示吸气画）。
说话对白仍可用 `build-character-voice/scripts/align_placed_dialogue.py`；唱段用本脚本。

### 2. `scripts/probe_viewer_states.mjs` + `scripts/check_av_sync.py` —— 声画同步探测

```
node probe_viewer_states.mjs "<viewer-url>?capture=1" T0 T1 states.json
python check_av_sync.py states.json 成片.mp4 --align alignment.json --beats beats.npy --mix mix.wav --t0 T0 --who noya
```

viewer 的 `stepAt(t)` 必须逐帧返回**实际显示**的嘴：
`{shot, drawings|face, <who>:{faceVisible, mouth, eyes}}`；原画画死的嘴报 `mouth:'drawn'`，
不得报计划值。检查器的真值全部来自音频与成片像素：

- 口型：**开合度 vs 人声能量相关**（首要，观众读「同步」主要读开合随声强起落）、每秒换嘴次数、
  休止张嘴帧、有声闭嘴帧、画死嘴帧、韵母口型类匹配率、逐字起音时差
  （显示正确嘴形首帧 − 字起点，门：−70~+100ms）。
- 表情：句前吸气是否出现；唱中眨眼。
- 动作：每镜头停帧分布、换画落八分音符 ±1 帧比例、平均换画跳变（成片逐帧差分）。
- 协调：Beat Align Score（动作重音=换画∪运动峰，对四分+八分网格，σ=50ms）；
  画面运动能量与混音起音强度的互相关及最佳时滞。

### 3. `scripts/audio_report.py` —— 分层音频报告

```
python audio_report.py --layer vocal:noya=noya.wav --layer music:bed=bed.wav \
  --layer ambience:room=bed_placed.wav --layer foley:fx=foley.wav --layer mix:mix=mix.wav \
  --window 30 38 --text 已知台词 --cues foley_cues.json --aesthetics --out report.json
```

- 全层：EBU R128 积分响度、LRA、真峰值；可选 Audiobox 审美四分。
- 配音/唱段：有声比、音高中位与音域、停顿、颤音深度、ASR 字错率（同音字会计错，需人看）。
- 配乐：速度与拍间隔 CV、调性估计、逐小节响度弧线、起音密度、段落边界。
- 环境床：与 build-ambience-foley 三门同口径（max/mean<1.4、周期性<0.15、嘶声<0.2）；
  门限针对**混音中实际放置的底床**，原素材数值只作参考。
- 拟音：起音列表；给 `--cues` 时列出偏离 ±0.15s 的 cue。
- 层间：人声↔配乐语音带 SMR 中位、被遮蔽帧占比、配乐在人声下的避让 dB。
- 素材短于窗口（不在时间线坐标上）时自动整段分析并标 `window:null`。

## 工作流

1. 锁定最终放置的分轨（人声/配乐/环境/拟音）与混音，记 sha256。
2. `audio_report.py` 出分层报告，先过各层硬门（响度、遮蔽、底床三门、拟音 cue）。
3. 有可见唱/说：`align_sung_lyrics.py` → viewer 消费 → 探针 → `check_av_sync.py`。
4. 改版前后用同一组命令对比（指标表进 NOTES/审片记录），只把**改善了的维度**说成改善。
5. 交付时写清：哪些由指标验证，哪些（节奏美感、音色、情绪）仍待用户实听。

## 踩坑记录

- **按字选嘴形≠同步**（星辰马戏团 R4→R4b，用户：「看起来是文生图做的，不是唇型同步做的」）：韵母匹配率 85%、
  起音时差全合格，但每字一形、长音整段冻嘴，开合与声强相关仅 0.48。改为借月光的少女同法——20ms RMS 包络、
  句内 p80 缩放阈值的三态迟滞、15fps 采样决定开合，字只决定圆唇/展唇形状，字内发声（擦音、渐弱尾音）至少窄口——
  相关升到 0.73。先看开合相关，再看韵母类。

- **能量决定开合、但韵母必须封顶形状**（星辰马戏团 R4c→R4d）：只对圆唇韵母锁形时，高能量的 i 字（「一」）被推成最大张嘴
  露舌 5 帧，用户读成「嘴型对不上字」。i/in/ing 上限窄口；介音复韵母（ie/uan/iao）字头先给介音形一个口型采样
  （1/15s；停 0.1s 会让起音超门）；ao/ou 长音尾段撮圆。韵母匹配 0.585→0.69，开合相关降 0.05 属预期代价——
  两者要一起报。查这类问题先做「嘴窗逐帧条带 + 字/能量标注」，比看汇总指标更快定位。
- **唱歌 DTW 偏差远超对白**（星辰马戏团 R4，2026-10-30）：「哪」被放进 33.4 的换气静音
  （实际起音 33.7），「旋/律」整体错一个音符；Whisper 词时间戳与 DTW 几乎一致，不能当独立核验。
  按声母类型匹配地标（擦音声母配擦音爆发，其余配浊音/换音/能量谷）后与逐帧读谱结果一致。
- **换气不是字**：擦音样噪声后 0.15s 内无浊音 = 吸气，不参与字界吸附，单独输出供表情。
  弱起长音（「吸」x 擦音 0.4s 后才起声）门限过高会误判成换气，浊音门用 0.14（段内归一）。
- **句尾长音不能被裁句截断**：句窗 end 截在长音中间，末字结束被钳到窗口，口型提前闭嘴；
  end 宁长勿短，靠能量判有声尾。
- **肖像底图本身是微张嘴**时，"rest"映射到底图仍是张嘴，休止帧计为张嘴；要么有真闭口变体，
  要么在报告中如实计数。
- **有限动画的"跳帧比"天然很高**（两次换画之间几乎无运动），比较改版用绝对的平均换画跳变与停帧分布。
- **Audiobox Aesthetics 安装**：`pip install audiobox_aesthetics`（只增 3 个小包，不动 torch）；
  torchaudio 2.x 读盘依赖 torchcodec 的 FFmpeg DLL，Windows 上常缺——用 librosa 读成张量传
  `{"path": tensor, "sample_rate": sr}`。底床/拟音 CE≈3 是正常的（不是"好听"的素材），只做同类回归比较。
- 退役：`dula-assets/lib/audio/review_audio.py` 走百炼 qwen-omni，通道已弃用，不再作为听审证据。
