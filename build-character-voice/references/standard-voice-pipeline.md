# 标准配音工艺链（火山-only，2026-11-05 监制令落盘）

> 配音/环境音/音效一律火山（seed-tts-2.0 + Seed-Audio）；算法合成与 edge-tts
> 播音腔不进正片。本链是 9章（bio_armor_academy_s1e1→s1e3）与星屑战壳
> （stardust_clad_op R12 / s1e1 R13）实战定型的流水线标准；参数只引用，
> 剧集私有数据（台词/声线定案）留在剧集目录，别拷进 skill。

## 0. 管线总览（顺序不可乱）

选声 → 语境化逐句演绎 → 合成（缓存三元组）→ 逐句后期 → QC → 摆点进混音 → 口型派生 → 复验
任何一环改了上游，下游全部重派生（时长/末字时刻/口型包络都变）。

## 1. 选声（选演员，不调参捏演员）

1. 查音色目录的设计戏路（陪伴/活泼/叙事/新闻）——叙事腔音色不给对话多的角色
   （xiaoju_secret 教训：F0 只能筛年龄段，筛不出表现力）。
2. 演绎型筛选：同两句代表台词（一句平静、一句情绪点）生成 2-3 候选盲听 A/B。
   执行环境无音频输入能力时，明确写"暂定接片、戏感待监制耳朵"，不许写成已听审。
3. 主角可用 ICL 克隆音色（`ICL_*` 直接挂 seed-tts-2.0 resource 合成；
   星屑战壳 R12 实测 rexueshaonian/aomanjiaosheng 直出）；新克隆音色先跑一句小样本。
4. 喊招/嘶吼等超出 TTS 上限的表演，改走 Seed-Audio 演绎生成（prompt 公式：
   角色状态→嗓音物理→念法→台词原文）+参考音频锁音色，满意后复刻固化。

参考实现：`bio_armor_academy_s1e1/tools/audition_*.py`（批量试听）、
`dula-skills/volc-voice-casting/`（音色目录+ListSpeakers）、
星屑战壳两集 NOTES 选声定案表。

## 2. 语境化逐句演绎

- 逐句 `delivery = {rate, context}`：rate 用 seed-tts 原生 speech_rate（-50..100），
  context 是 TTS 2.0 自然语言演绎指令（「冷冽宣告终结技，压迫感」级）。
  **别用后期 atempo 调速充演绎**（音高/共振峰全塌）。
- 情绪变体表拉开档位：default/nervous/shout/冷傲/破功各档 rate 差 ≥10，
  全压 1.0 附近=端着。喊招档 rate +10~25 高压炸场；冷面档 −5。
- TTS 输入保留标点（标点=停顿）；数据模型三分离：text（纯字供 QC）/
  display（字幕）/tts_text（TTS 输入）。
- 拟声笑声 ASR 不稳：用单字「哈！」；QC 以拼音内容覆盖率为准。

参考实现：`stardust_clad_s1e1/config/dialogue.json`（逐句 delivery 实表）。

## 3. 合成与缓存三元组

- 逐句 `tag = sha256(text|speaker|delivery)`，tag 未变 skip-if-exists——
  整集重铸也只重录变化句（R12/R13 实测：22 句只重录 11 句变速档）。
- 每句留 `.source.json` 溯源（text/speaker/delivery/tag/sha256/provider）。
- 稍长台词超窗时：先保留内在停顿、调整时间轴可用窗口，再考虑提速；
  不截词尾、不给 QC 偷偷加大不存在的窗口。

参考实现：`stardust_clad_s1e1/tools/gen_dialogue.py` + `config/dialogue.json`、
合成正本 `dula-skills/volc-voice-casting/scripts/seedtts_say.py`。

## 4. 逐句后期（进混音总线之前）

- 逐句峰一化（.5~.55 峰值）再进 voice_gain——响度统一在后期做，不在混音器补救。
- 喊招顶格后若触发整体归一属预期；混音峰值上限 −2.2dBFS（保 AAC ≤0.8，R2 教训）。
- SOX/ffmpeg 只做 EQ/动态/距离/轻房间感；不用后期 pitch/formant 捏年龄性别。

参考实现：`stardust_clad_s1e1/tools/build_audio.py`（峰一化+duck 总线）、
`bio_armor_academy_s1e3/tools/remix_audio.py`（峰一化 .55 正本）。

## 5. QC（机器判全绿才入库，不打扰监制逐条听）

工具：`dula-skills/volc-voice-casting/scripts/qc_lines.py`（manifest 驱动）。
判定域：拼音重合率 ≥85% ✅（60-85 ⚠️）/ 时长在窗（超窗 >0.2s ❌）/
峰值 0.15-0.99 / nonverbal 非静音占比 >50%。
- **必须比拼音不能比汉字**（战损气声必出同音字）；同音字坑按拼音判例放行并记录。
- 时长窗=到下一句起点的真实窗口；超窗句的修法是重排谱面/变速档，不是放窗。
- 混音后复验：AAC 解码峰值 ≤0.8（编码过冲留量），onset 对位见环境音工艺末节。

## 6. 口型派生（同一零点铁律）

- viewer 链：从最终放置的同一 PCM 分轨派生 10-20ms 能量包络轨（能量开合，
  不是音素视素）；静默帧口型必须为 0；包络文件与混音同一零点。
- 帧链：DTW 逐字对齐回写时间轴（`dula-assets/lib/audio/` 正本，别跨集拷贝）。
- 任何摆点/时长变更后，口型包络必须重派生、视频随包络重渲。

参考实现：`stardust_clad_s1e1/tools/build_audio.py`（voice_envs.json 派生）、
`bio_armor_academy_s1e1/tools/build_lipsync.py`（DTW 链）。
