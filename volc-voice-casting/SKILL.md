---
name: volc-voice-casting
description: 火山配音大模型（seed-tts-2.0）角色选声与声音复刻固化——构建音色目录（ListSpeakers 拉全 + 演绎型/资讯型关键词分类）、按角色需求筛选、批量试听合成（逐句 mp3 + 时长窗口对比 ✅/⚠️）、未解锁音色自动生成"待解锁清单"、把已验收的演绎参考音频克隆成专属 Speaker ID（v3/voice_clone + get_voice 轮询 + F0 对比验证）长期固定调用。给剧集角色选 TTS 声线、验收演绎后固化角色音色时用。
---

# Volc Voice Casting（火山配音大模型角色选声）

把 seed-tts-2.0 的"选声"流程自动化：音色目录 → 筛选 → 批量试听 → 决策写回。
权威接入备忘是 `dula-skills/build-character-voice/references/volcano-seedtts.md`
（端点、鉴权、resource 配对、emotion 参数纪律），本 skill 只解决"选哪个音色"。

解释器统一用 `dula-story/.venv/Scripts/python.exe`（volcengine SDK 已装）。
签名凭证脚本自动解析 `dula-story/.env.cv`；合成需要 speech key：

```bash
set -a && source dula-story/.env.speech && set +a   # 裸 KEY=value，必须 set -a
```

## 工作流（四步）

### 1. 构建/刷新音色目录

```bash
dula-story/.venv/Scripts/python.exe dula-skills/volc-voice-casting/scripts/build_voice_catalog.py
```

- 复用 volc-balance 的 ListSpeakers（Version=2025-05-20）分页拉全 seed-tts-2.0
  全部音色，按 Name+Description 关键词打 `category` 标签（演绎型/资讯型/其他，
  关键词表在脚本顶部 `CATEGORY_KEYWORDS` 常量，可直接维护）。
- 落盘 `references/voice_catalog.json`（含 fetched_at、总数、分类统计）；
  stdout 默认打印演绎型男声摘要表。
- 过滤打印：`--gender 女 --category 资讯`；原始 JSON：`--json`。

### 2. 按角色需求筛选

从 catalog（或上一步的摘要表）按角色设定挑候选：性别、年龄、演绎型、
`[多情感:...]` 标签（需要 emotion 的角色必须选多情感音色）、Description
气质关键词（冷/沉/狠/甜/痞等）。ICL 复刻音色不在 seed-tts-2.0 resource 下，
本目录不含它们。

### 3. 批量试听

```bash
# 显式候选音色 + 指定台词 + 目标窗口
dula-story/.venv/Scripts/python.exe dula-skills/volc-voice-casting/scripts/audition_voices.py \
  --text "学生会命令：9章，今晚回收。" \
  --voices zh_male_xxx_bigtts,zh_male_yyy_bigtts \
  --window 4.8 --out dula-story/episodes/<ep>/tmp/voice_audition/v1

# 从剧本提取某角色全部台词（窗口自动取 SRT 时间轴），按分类圈选音色
.../audition_voices.py --episode dula-story/episodes/<ep> --character 角色名 \
  --category 演绎 --gender 男 --emotion sad --emotion-scale 2 \
  --out dula-story/episodes/<ep>/tmp/voice_audition/v2
```

- 每个 音色×台词 组合出一条 mp3（同名覆盖、单条失败继续），用 ffprobe
  测时长并与窗口对比标 ✅/⚠️。
- 结尾输出 markdown 试听报告（同时写 `<out>/report.md`）。
- **未解锁音色（403 not granted）不中断**，自动汇入报告末尾的
  "待解锁清单"——解锁没有公开 OpenAPI，拿清单去控制台「语音合成2.0」
  音色广场人工 0 元下单，下完重跑即可。

### 4. 人工试听决策，写回剧集配置

试听 mp3 选定后，写回 `dula-story/episodes/<ep>/config/voice_config.json`，
格式参考 `dula-story/episodes/yuki_bento_battle/config/voice_config.json`
的 seedtts provider：

```json
{
  "角色名": {
    "default": {
      "provider": "seedtts",
      "resourceId": "seed-tts-2.0",
      "speaker": "<选定的 VoiceType>",
      "format": "mp3",
      "sampleRate": 24000,
      "volume": 50
    }
  }
}
```

## 已知坑（务必读）

- **禁止播音腔（2026-09-26 导演硬规矩）**：资讯/通用/播报/**解说**类音色
  一律不得进正片——包括 F0 再低也不行的"磁性解说"类，解说腔的本质是
  旁白不是角色。角色台词只有两条合法路径：① 角色演绎类 TTS 音色
  （标签为有声书/广播剧/影视角色）+ emotion；② Seed-Audio 演绎
  （见下节）。白岚案例：TTS「高冷沉稳」F0 触底仍被判播音腔，换
  Seed-Audio 演绎通过。选声时"数据合格"不等于"戏合格"，导演耳朵是
  最终裁决。

- **resource 配对**：seed-tts-2.0 音色只能配 `X-Api-Resource-Id: seed-tts-2.0`；
  ICL 复刻音色（`ICL_*`）挂在别的 resource，配错报 55000000 resource
  mismatch。本目录只含 seed-tts-2.0 音色，天然规避。
- **emotion 生效要验证**：API 不报错不代表参数生效。换 emotion/scale 后
  对比输出文件 md5，有差异才说明真的生效（详见证词见
  build-character-voice/references/volcano-seedtts.md）。
- **emotion_scale=2 弱档最稳**：能出戏感且不易性别漂移；个别音色有漂移
  前科，逐音色试听验证，不要批量信任。
- **无 rate 控制**：V3 单向 HTTP API 不支持调速。时长超窗（⚠️）只能
  精简台词或加宽剧本槽位，别无他法。
- **空成功坑（2026-09-26 选声实测）**：部分音色对不支持的文本语言不报错——
  流式响应返回 `code:0` + `code:20000000` 成功哨兵但 `data` 全为 null，
  零音频块。实测 `fr_male_fr_m29`、`en_male_chandler_p1` 喂中文台词即如此。
  audition_voices.py 会把这类归为"合成失败（空成功坑）"，看到它不是
  网络问题，是音色与文本语言不匹配，换音色或换文本。
- **凭证两套别混**：ListSpeakers 用 IAM AK/SK（`.env.cv`）；合成用语音
  控制台 API Key（`.env.speech` 的 `VOLC_SPEECH_API_KEY`），与 ARK key
  不通用。两个 .env 都是裸 `KEY=value`，bash 里要 `set -a; source; set +a`。
- **绝不在输出/日志/报告中打印任何密钥内容。**
- **气声字会被念成本音（2026-09-26 战损声实测）**：想让角色"带喘息"时，
  文本里写「嗬/呃/咳」会被 TTS 字正腔圆地读成 hē/è/ké（像笑场），不是
  气声。喘息只能来自两条路：① 纯标点断句（「白……岚……部……长……」）
  让模型自己出停顿气口；② 后期叠 Seed-Audio 生成的喘息 foley 轨
  （volume 0.3-0.4 amix 垫在干声下）。
- **中文男声无 native 沙哑音色（2026-09-26 全量目录实测）**：catalog 里
  沙哑/嘶哑标签的音色全是外语或女/老年声。中文少年/青年沙哑只能靠
  后期链（参考链：降调 0.95 + acrusher bits=11 轻削波 + lowpass 7500 +
  轻压缩），或声音复刻克隆目标表演。
- **Whisper 同音字坑（2026-09-26 QC 实测）**：战损气声台词经 Whisper 转写
  会得到同音字（「白岚部长」→「白蓝不长」），发音其实正确——转写核对
  **必须做拼音级比对**（去声调拼音序列相似度），比汉字会把合格演绎误判
  成失败。qc_lines.py 已内置，阈值见「自动化验收纪律」。

## 表演化台词：Seed-Audio 演绎路径（2026-09-26 验证定案）

TTS 合成（seed-tts-2.0）的天花板是"干净朗读 + emotion 微调"，调不了
**音色物理属性**（沙哑、血沫气音、破音）。遇到战损、嘶吼、濒死这类
表演强度超过 TTS 能力线的台词，改走 **Seed-Audio 生成式演绎**：

```
seedaudio_gen.py --prompt "生成一段<N>秒纯人声台词录音，无音乐无音效无背景声：
  <角色状态>，<嗓音物理描述>，<念法>，说：<台词>" --out <line>.wav
```

prompt 公式四要素：**角色状态**（受重伤的十七岁少年）→ **嗓音物理**
（嘴角带血、嗓音嘶哑气弱）→ **念法**（一字一喘艰难地）→ **台词原文**
（标点断句保留，如「白……岚……部……长……」）。

纪律与局限：

- **必须声明"纯人声、无音乐无音效无背景声"**——保护分轨混音与口型
  管线；绝不使用它的"对白+音效+配乐一条出"模式。
- **音色不可复现**：每次生成都是新"演员"。只适用于角色全程处于同一
  特殊状态的短片（如全程重伤）；系列正片要长期保持沙哑声线，须把最
  满意的一条演绎作为参考音频走**声音复刻 2.0** 固化成专属音色再回 TTS。
- 与 TTS 路的取舍：常态台词走 TTS（音色固定、可批量）；特殊状态台词
  走 Seed-Audio 演绎（表演上限高）。同一片子两路可混用。
- 验证案例：bio_armor_academy_s1e1《9章》30s 打斗试片，雷晓战损台词
  与暴走嘶吼均走此路径，导演验收"完全达到要求"（2026-09-26）。

## 参考音频锁音色（scripts/seedaudio_acted.py，2026-09-26 实测）

Seed-Audio 1.0 原生支持参考生成：把验收过的演绎音频当参考随请求上传，
逐次锁定角色声线——**替代 138 元/个的复刻音色槽位的低成本路线**
（监制已定：先走这条）。

**何时用 vs 槽位的取舍**：
- 参考音频锁：零额外成本、随生成随锁，适合每集只有几句特殊状态台词；
  缺点是逐次生成仍有音色漂移（见实测），不能当全局固定声线。
- 音色槽位（声音复刻固化）：全局固定、长篇正片多戏份必选项；
  138 元/个，走 `clone_voice.py`（当前卡在控制台开通音色服务）。

**接口字段实测结论**（[音频生成HTTP 文档](https://docs.volcengine.com/docs/6561/2550782)，一次打通）：
- body 加 `references: [{"audio_data": "<base64>"}]`（与 `speaker`/`audio_url`
  三选一互斥；图片参考不能与音频参考混用）。
- prompt 里用 **`@音频N`** 引用参考（N 从 1 开始，与 references 上传顺序
  严格对应）。
- 上限：3 条参考、单条 ≤30s、≤10MB，wav/mp3/pcm/ogg_opus。
- `audio_config` 另有 `speech_rate`/`loudness_rate`/`pitch_rate` 可调
  （seedaudio_gen.py 时代的认知里没有这三旋钮，此处补充）。

```bash
seedaudio_acted.py --prompt "生成一段4秒纯人声台词录音，无音乐无音效无背景声：
  参考@音频1里的重伤少年，同样嘶哑气弱地念出：<台词>" \
  --ref <验收音频.wav> --out <line>.wav
```

**验收口径**：内容走 qc_lines.py（拼音级）；音色延续用 librosa 对比参考与
输出的 F0 中位数（比值 0.9~1.1）与谱质心（偏差 <15%）。

**实测（雷晓战损声，ref=S1_acted_v1.wav，3 次生成）**：

| 版本 | QC 内容 | 谱质心偏差（vs S1 3510Hz） | 结论 |
|------|---------|---------------------------|------|
| v1 | ❌ 念错词（明天放学→明天发射，拼音 50%） | **14.0%（达 <15% 口径）** | 音色锁住了但内容失败 |
| v2 | ✅ 拼音 100%（明天放雪=同音字） | 60.8% | 内容绿、音色严重跑偏 |
| v3 | ✅ 拼音 100% | 24.6% | 内容绿、音色接近但仍偏亮 |

- prompt 里**必须明说台词文本本身**（「台词就是『明天放学』四个字，不要
  念成别的词」），否则省略号断句法会被自由发挥成同音错词。
- **如实结论**：参考锁定零成本、对"内容+大致风格"有效，v1 证明音色
  物理延续也能达标（谱质心 14.0%）——但**内容与音色同时达标不稳定**
  （3 次各有一次内容错、一次音色飞、一次音色偏亮 24.6%）。可用，代价是
  要按 QC 纪律多刷几次挑双绿的；极端沙哑气声音色尤其如此。**正片雷晓
  若戏份多，保留 138 元槽位购买建议**（控制台开通音色服务后走
  clone_voice.py，全局固定免刷）。
- F0 比值在气声素材上不可作依据（S1 参考的 pyin 中位数 65Hz 是次谐波
  假象），看谱质心。

## 声音复刻固化（scripts/clone_voice.py）

**何时用**：演绎路径（Seed-Audio 生成 → 导演验收某条演绎音频）走通后，
把那条验收音频克隆成专属 Speaker ID，之后当普通 TTS 音色固定调用——
一条 5 秒验收音频换长期稳定的角色声线，不用每次重新演绎。
衔接链路：演绎 → 验收 → 复刻固化 → 回 TTS 固定调用。

```bash
set -a && source dula-story/.env.speech && set +a
dula-story/.venv/Scripts/python.exe dula-skills/volc-voice-casting/scripts/clone_voice.py \
  --ref <已验收.wav> --speaker-id <自定义ID> --name "角色·状态" \
  --verify-text "测试台词" --out <episode>/tmp/voice_audition/vN_clone/
```

流程：上传训练（`/api/v3/tts/voice_clone`）→ 轮询状态
（`/api/v3/tts/get_voice`，10s 间隔，10 分钟超时，status=2 Success / 4 Active
可合成）→ 自动合成验证（resource 候选 `seed-tts-2.0` → `seed-icl-2.0` 依次实测，
首个可用值记档）→ librosa F0 中位数对比参考音频（比值 0.9~1.1 为同音高区间）
→ 追加写入 `references/cloned_voices.json`。

### 实测结论（2026-09-26）

- **鉴权：X-Api-Key 可用**，新版复刻 API（v3/voice_clone、v3/get_voice）与
  seed-tts 合成同一把 `VOLC_SPEECH_API_KEY`，**不需要**旧版的 AppID/Bearer
  Token（那是旧控制台 `/api/v1/mega_tts/*` 接口的体系）。
- **音色服务要单独开通**：本账号已开通语音合成2.0，但训练提交仍报
  `45000030 [resource_id=volc.megatts.timbre] requested resource not granted`
  ——「豆包声音复刻模型2.0」之外的**「音色服务」（后付费音色）需在控制台
  开通管理里单独手动开通**，开通后无需改凭证直接重跑。
- speaker_id 传参形态：后付费自定义音色 body 里 `speaker_id` 固定传字面量
  `"custom_speaker_id"`，实际 ID 放 `custom_speaker_id`。命名规范：字母开头、
  8~256 位、仅 `[a-zA-Z0-9_-]`、不能撞官方前缀（S_/ICL_/两字母+_ 等）与
  `_tob/_bigtts` 后缀（脚本内置校验）。
- **计费坑（官方口径）**：克隆音色首次调用合成接口即"转正"并收音色槽位费，
  确认试听满意前别拿它跑正式批量合成；每个音色有训练次数上限（响应里
  `available_training_times`，免费赠送额度为 15 次）。
- 参考音频要求：≤10MB，wav/mp3/ogg/m4a/aac/pcm（pcm 仅 24k 单通道）；
  可传 `text` 做 WER 校验（差异大报 45001109）。

## 自动化验收纪律（监制制度）

**原则**：QC 全绿（✅）直接入库进混音，不打扰监制；QC 红（❌）由 AI 自行
换音色/换演绎重生，直到转绿；**只有 QC 无法判定的情况才上报监制**，
目前明确两类：

1. 同一句多个候选 QC 全绿时的「戏感二选一」（机器判不出戏感高下）；
2. 连续 3 次重生仍 QC 红（生成路径本身有问题，需要人决策）。

工具：`scripts/qc_lines.py`（faster_whisper small/cpu/int8 转写 + pypinyin
拼音比对 + librosa 电平/F0，全本地，不需要任何 key）。

```bash
# 直接命令行（dialogue 类）
dula-story/.venv/Scripts/python.exe dula-skills/volc-voice-casting/scripts/qc_lines.py \
  --expect "白岚部长@<episode>/assets/audio/fight_01_leixiao.mp3" --window 5.0 \
  --out-report <episode>/tmp/voice_audition/qc_report.md
# 或 manifest（可混 dialogue/nonverbal，逐条窗口）
.../qc_lines.py --manifest qc.json --out-report qc_report.md
# qc.json: [{"file": ..., "expect_text": null|str, "window_s": null|float,
#            "kind": "dialogue"|"nonverbal"}]
```

退出码：全 ✅=0，有 ⚠️=1，有 ❌=2（可直接接管线条件判断）。

### 指标口径（阈值与 qc_lines.py 顶部常量一致）

| 检查 | ✅ | ⚠️ | ❌ |
|------|----|----|----|
| 时长 vs 窗口 | 低于窗口 0.2s 以上 | 临界 ±0.2s（含恰好顶格） | 超窗 >0.2s |
| 峰值电平 | 0.15~0.99 | <0.15（混音需补偿） | >0.99（削波） |
| 拼音重合率（dialogue） | ≥85% | 60~85% | <60% |
| 非静音占比（nonverbal） | >50% | ≤50% | — |

F0 中位数与 P10-P90 只报告不判定（气声/嘶吼的 F0 跟踪不稳定，不作依据）。

### 实测（2026-09-26，bio_armor_academy_s1e1 三条正式音频）

- `fight_01_leixiao.mp3`（预期「白岚部长」）：转写「白蓝不长」——同音字坑
  实锤，汉字比对会误判 ❌，**拼音重合率 100% ✅**。拼音级比对是刚需。
- 三条时长全部恰好顶格窗口（5.00/5.00、3.00/3.00）→ 临界 ⚠️：Seed-Audio
  按目标时长生成的典型表现，不是缺陷，但提示窗口零余量，混音对齐时注意。
- 气声台词 pyin 易跟到次谐波（实测中位数 65 Hz，P10-P90 仅 2Hz 宽），
  所以 F0 只看不判。

## 翻车写回纪律

遵循 `dula-skills/AGENTS.md`：试听/合成过程中发现的新坑（新的错误码、
音色行为异常、解锁流程变化等），任务收尾时写回本 SKILL.md 的"已知坑"
或新增"翻车记录"一节并提交。
