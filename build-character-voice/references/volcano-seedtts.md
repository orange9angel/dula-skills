# 火山引擎豆包语音（seed-tts-2.0）HTTP 接入备忘

> 来源：2026-08-29 实测接入。用途：给剧集增加 CosyVoice 之外的第二配音通路
> （豆包大模型音色支持 emotion + emotion_scale 情感参数，CosyVoice 没有）。

## 与方舟的关系

语音服务**不在火山方舟**（ark.cn-beijing.volces.com 那套不管它）。
它在"语音技术"独立控制台：

- 开通服务：[服务开通](https://console.volcengine.com/speech/new/setting/activate?projectName=default)
  —— 对应产品叫**「语音合成2.0」**（控制台里没有"Doubao TTS"这个名字），
  顺带可开「声音复刻2.0」（克隆自定义音色）和「音频生成1.0」（待探）。
- 拿 key：[API Key 管理](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default)，
  与 ARK_API_KEY **不通用**。
- 音色坑：除 BV001/BV002_streaming 外，**免费音色也要在控制台"下单支付 0 元"解锁**，
  否则报 403 not granted。

## 调用形态（V3 HTTP 单向流式，实测可用）

```text
POST https://openspeech.bytedance.com/api/v3/tts/unidirectional
Headers:
  X-Api-Key: <语音控制台的 key>
  X-Api-Resource-Id: seed-tts-2.0
  Content-Type: application/json
Body:
  {"user": {"uid": "any"},
   "req_params": {"text": "台词",
                  "speaker": "zh_female_vv_uranus_bigtts",
                  "audio_params": {"format": "mp3", "sample_rate": 24000},
                  "emotion": "...", "emotion_scale": 1-5}}
```

- 响应是**逐行 JSON 流**（每行一个对象，`data` 字段是 base64 音频分块），
  逐行 `json.loads` 后拼接 `base64.b64decode(data)`。整段 `json.loads` 会报
  Extra data。
- **speaker 和 resource id 要配对**：不同音色挂在不同 resource 下，配错报
  `resource ID is mismatched with speaker related resource`。实测
  `seed-tts-2.0` + `zh_female_vv_uranus_bigtts` 通过；jupiter/mars 不挂在这个
  resource 下。选音色前先确认它属于哪个 resource（控制台音色广场有标注）。
- 认证失败 vs 未开通的区分：`requested resource not granted` = 服务/音色没开通
  或没 0 元下单；401/格式错误才是 key 问题。
- 文本上限 1024 字节（建议 <300 字符）；每次 reqid 必须唯一。
- 情感参数：`emotion` + `emotion_scale`（1-5）+ 需 `enable_emotion: true`，
  支持的情感范围按音色不同，见官方"多情感音色"列表。

## 与 CosyVoice 的分工（当前剧集现状）

- CosyVoice 龙华 = 小蓝当前声线（E01-E03 已定型），不动。
- 豆包 seed-tts-2.0 = 新角色/多声音需求时的第二通路；情感参数适合做
  情绪起伏大的台词。接入样例（含分包解析）：dula-story/tmp/douyin/
  volc_tts_sample.mp3（2026-08-29 "太阳要下山了呢" 实测 4.2s 通过）。
