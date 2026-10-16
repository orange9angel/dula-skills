# 火山引擎豆包语音（seed-tts-2.0）HTTP 接入备忘

> 来源：2026-08-29 实测接入。用途：给剧集增加 CosyVoice 之外的第二配音通路
> （豆包大模型音色支持 emotion + emotion_scale 情感参数，CosyVoice 没有）。

## 与方舟的关系

语音服务**不在火山方舟**（ark.cn-beijing.volces.com 那套不管它）。
它在"语音技术"独立控制台：

- 开通服务：[服务开通](https://console.volcengine.com/speech/new/setting/activate?projectName=default)
  —— 对应产品叫**「语音合成2.0」**（控制台里没有"Doubao TTS"这个名字），
  顺带可开「声音复刻2.0」（克隆自定义音色）和「音频生成1.0」（Seed-Audio，
  已接通，见文末）。
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
                  "audio_params": {"format": "mp3", "sample_rate": 24000,
                                   "emotion": "happy", "emotion_scale": 2},
                  "additions": "{\"context_texts\":[\"温柔、带笑意地与同学交谈\"]}"}}
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
- 情感参数放在 `req_params.audio_params` 内，按音色支持范围使用。
  旧脚本把它们放在 `req_params` 根层并加 `enable_emotion`，不是当前文档契约；
  请求成功不能证明旧参数起效。TTS 2.0 的自然语言导演指令使用
  `req_params.additions.context_texts`，其中 `additions` 是 JSON 字符串。

## 与 CosyVoice 的分工（当前剧集现状）

- CosyVoice 龙华 = 小蓝当前声线（E01-E03 已定型），不动。
- 豆包 seed-tts-2.0 = 新角色/多声音需求时的第二通路；情感参数适合做
  情绪起伏大的台词。接入样例（含分包解析）：dula-story/tmp/douyin/
  volc_tts_sample.mp3（2026-08-29 "太阳要下山了呢" 实测 4.2s 通过）。

## 音频生成1.0（Seed-Audio 1.0）——2026-08-29 深夜接通

- **端点**：`POST https://openspeech.bytedance.com/api/v3/tts/create`（非流式，
  JSON 响应里 `audio` 字段是 base64 音频整段，不是流式分包）。
- **鉴权**：同一把语音控制台 key（`X-Api-Key`），**不要走方舟**——方舟
  tasks 接口对 `doubao-seed-audio-1-0` 返回 404（无邀测权限的账号）。
- **请求体**：`model: "seed-audio-1.0"` + `text_prompt`（≤3000 字符，可用
  自然语言指定总时长）+ `audio_config: {format: wav/mp3, sample_rate:
  ≤48000}`。最长 120s。成功时 `code` 字段缺省（20000000=成功哨兵，
  别当错误）。
- **定位**：单要素模式出纯环境音/纯 BGM stem（保护分轨混音与口型管线）；
  它的招牌"一条 prompt 出对白+音效+配乐成品"模式与我们的管线冲突，别用。
  **例外（2026-09-26 验证）**：纯人声"演绎化台词"stem 可用——prompt 声明
  "无音乐无音效无背景声"，直接描述角色状态/嗓音/念法生成表演化对白
  （战损嘶哑、嘶吼等 TTS 达不到的表演强度），仍是单要素 stem，不进混音冲突。
  局限是音色不可复现，详见 volc-voice-casting/SKILL.md「表演化台词」一节。
- 接入脚本：dula-story/episodes/cat_leads_e04_firefly_night/tools/seedaudio_gen.py。
- E04 实测：虫鸣/夜风/BGM 三个 60s stem 均一次成功（详见该集 V1_NOTES）。

## seed-tts-2.0 补充（2026-08-29 深夜实测）

- 响应流里 `code: 20000000` 是**成功**哨兵（终态帧），客户端要放行。
- 猫声线选定：`zh_female_mizai_saturn_bigtts`（黑猫侦探社咪仔）挂在
  `seed-tts-2.0` resource 下可用；`ICL_*` 复刻音色不在此 resource
  （报 55000000 resource mismatch）。

## E05 全角色迁移 verdict（2026-09-05，cat_leads_e05_morning_sketch）

导演 A/B 判定 seed-tts-2.0 听感明显优于 CosyVoice v3-flash（后者无情感参数，
只有 rate/pitch/volume 三旋钮），E05 V2 起人类角色全部迁到 seed-tts-2.0：

- Girl = `zh_female_vv_uranus_bigtts`（Vivi 2.0）；Boy =
  `zh_male_taocheng_uranus_bigtts`（小天 2.0，少年音）；Cat 维持
  `zh_male_dayi_saturn_bigtts` 不挂情感（E04 性别漂移教训）。
- **情感参数纪律：emotion_scale=2 弱档**。弱档能出戏感且最稳；实测
  happy/calm/surprised/tenderness 在 uranus 和 taocheng 上都有效且
  无性别漂移（E04 的漂移是个别音色问题，不是模型问题——但仍要逐音色
  试听验证。随机合成即使参数相同也可能产生不同文件，摘要变化只证明文件不同，
  不能证明情感控制生效）。
- 新验证可用的音色（seed-tts-2.0 resource 下已解锁）：
  `zh_female_xiaohe_uranus_bigtts`（小何）、`zh_male_m191_uranus_bigtts`
  （云舟）、`zh_male_taocheng_uranus_bigtts`（小天）、
  `zh_male_ruyayichen_uranus_bigtts`（儒雅逸辰）。
- **语速控制更正（2026-10-17）**：当前 V3 文档提供
  `audio_params.speech_rate`，范围 `-50..100`，`0` 为原速；旧“没有 rate”结论过时。
  本集接通自然语言指令，原生速率先用 `0`。原生调速与后期 atempo 不重复叠加；
  时长仍以最终 PCM 验证，不截断台词。
- **换音色/换情感后必须重跑全部 omni 镜头**：OmniHuman 视频的口型由旧音频
  驱动，幂等跳过逻辑会掩盖失同步——删 tmp/omni*.mp4 和 assets/omni/<shot>/
  重跑，别只重跑改过的那几句对应的角色镜头清单要按"音频变了的角色"算。

## 2026-10-17：导演配置必须进入实际请求

S1E4 的自有合成器只消费情感标签，未消费关系、意图与能量，且强度写死。
现用 `volc-voice-casting/scripts/seedtts_say.py` 将情绪放入正确层级，支持
`context_texts` 和原生语速；七句男声实际调用成功，内容检查通过。
将请求格式版本、指令、声线及速率全部纳入缓存键，保存不含密钥的请求元数据。
只改男主时显式选角色，保留女主已验收音频，不借公共接口修复顺手全量重生。
官方接口依据：[V3 HTTP 文档](https://docs.volcengine.com/docs/DoubaoVoice/HTTPChunkedSSEUnidirectionalStreaming-V3?lang=zh)。
