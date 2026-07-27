# DashScope TTS 迁移：Sambert → CosyVoice HttpTTS（2026-07 实测）

**旧通路已死**：`dashscope.audio.tts.SpeechSynthesizer` + `sambert-*-v1` 全部返回
`ModelNotFound`（dula-engine/tools/generate_audio_dashscope.py 及其 README 的 Sambert 预设随之失效，
在引擎修复前不要再走 `--provider=dashscope`）。

## 可用通路（华北2，按量计费约 ¥2/万字符）

```python
from dashscope.audio.http_tts.http_speech_synthesizer import HttpSpeechSynthesizer
result = HttpSpeechSynthesizer.call(
    model='cosyvoice-v3-flash',      # 或 cosyvoice-v3-plus / qwen-audio-3.0-tts-flash
    voice='longxiaoxia_v3',          # 音色与模型版本绑定：v3 用 *_v3，v2 用 *_v2
    text=..., format='wav', sample_rate=48000,
    rate=1.0, pitch=1.0, volume=50,  # 都支持，可做情绪变体（Sambert 路径只吃 model）
    stream=False, api_key=os.environ['DASHSCOPE_API_KEY'])
# stream=False 返回 result.audio_url（签名临时 URL）——立即下载，绝不写入持久文件
```

- 音色版本后缀必须跟模型匹配，混用报 engine error 418。
- 已验证中文女声：`longxiaoxia_v3`（龙小夏，知性积极，少女/旁白合适）、`longxiaochun_v3`（龙小淳，温柔知性）。
- 官方参考实现：`dula-story/episodes/rainy_rooftop_cat/tools/generate_audio_cosyvoice.py`
  （含 manifest schema、0.2s source-trim 约定、与模板管线兼容的混音）。
- 字级时间戳（word_timestamp_enabled）仅流式模式可用，且只支持 v3/v3.5 部分音色；
  做 lipsync 时本片用的是「对白总线能量包络 + 拼音 viseme」方案（tools/build_lipsync.py），不依赖字级时间戳。
