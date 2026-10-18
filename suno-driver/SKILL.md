---
name: suno-driver
description: Suno 网页版自动化（Playwright 持久会话）—— 无公开 API 时的 Suno 生成/下载驱动。需要自动化 Suno 抽卡、批量生成歌曲时使用。灰色地带：仅限自己的付费账号低频自用。
---

# Suno Driver（网页自动化）

## 本地凭据与下载真实性（2026-10-14）

- 用户明确授权保存凭据后，Windows 可用 `scripts/suno_credentials.py --store`
  将凭据保存到已忽略的 `.suno_profile/credentials.dpapi`，当前用户 DPAPI 加密。
  `--check` 只报告是否可用；登录脚本优先环境变量，其次读取加密存储。不要把密码
  写入记忆、技能、命令行或日志。加密写入和解密须处在相同 Windows 身份/执行上下文；
  沙箱身份保存的文件曾在沙箱外无法解密。加密保存不代表永远无需二次认证。
- Suno 播放器初始 `sil-100.mp3` 是静音占位，不是当前歌曲。`--download-id` 只接受
  对应 song id 的真实媒体源，并检查下载响应。文件存在、HTTP 200 或歌曲页显示
  正确标题都不能证明音频下载成功；还要解码、验时长与源摘要。S1E4 的占位下载已拒用。
- 生成器记录提交响应的状态与 clip id；点击按钮超时且没有 receipt 时，写“生成未确认”，
  不宣称成功。S1E4 后续通过常用浏览器取得生成回执和授权 WAV，见下节。

## 2026-10-17：真实浏览器提交与授权下载

- S1E4 持久无头会话可浏览作品，却在 Create 后失败或始终无生成回执；常用浏览器
  的 Kimi WebBridge 会话成功提交 v6，返回两个 clip id。保留明确失败/超时证据后
  切换已有登录的正常浏览器，不反复点击。仅点击或遮罩出现不代表任务已经创建。
- 新播放器可能使用 blob，`audio_url` 返回 `/api/forbidden`，媒体另含编码元数据。
  不提取/解码受保护播放流。正常路径是歌曲 **More options → 悬停 Download → WAV
  → Unlock & Download**；首次解锁消耗账号下载额度，已解锁歌曲可再次下载。
- UI 的合法下载响应返回 WAV 链接后，可直接保存该响应文件；临时签名 URL 不写入
  提交内容。检查解码、时长、声道、SHA，并记录 song id、生成回执与编辑参数。
  S1E4 实际取得 86.4s、48kHz 双声道 WAV；不能把早前的静音占位或失败记录当新结果。
- 同日咖啡厅音乐剧的菜单中，悬停 Download 没有展开，实际需要**点击 Download**
  才出现 MP3/WAV 对话框，再选 WAV、Unlock & Download。以当前快照里的对话框
  状态为准，不把某一次悬停成功当成固定 UI 契约；取得 75.56s 授权 WAV 后做解码
  与源摘要检查。角色唱段分工仍须听审，下载成功不代表分工提示被执行。
- `--download-id` 已补正常 WAV 对话框回退；按钮没有产生新 id 或明确报失败时停止，
  避免多个选择器连续提交同一任务。请求故障日志仅记录主机/路径/状态，不保存凭证。
  本机无头回退复测仍超时，不能写成 CLI 端到端成功；实际验证通过的是常用浏览器
  提交与 Unlock & Download 后保存合法 WAV 的通路。失败时保留对话框截图和阶段信息。

### 多行歌词编辑器（同日《冰箱前的最后一舞》实测）

- Lexical/contenteditable 歌词框的通用 `fill` 曾报告成功，却压平换行；`fill("")`
  也未清除框架内部内容，随后模拟粘贴又追加了重复歌词。提交前检查实际文本、分段
  与段落标记次数，不能只检查工具返回成功。
- 本机有效路径：CDP 启用焦点模拟并 focus 编辑框，用真实 Ctrl+A、Backspace 清空，
  确认只剩空行后用 `Input.insertText` 一次写入 UTF-8 多行歌词，最后关闭焦点模拟。
  检查实际行数和段落唯一性，再点击一次 Create；不要用 DOM selection + 合成 paste
  猜测替换成功。普通 style/title 文本框不受此问题影响。
- 生成后核对回执里的实际歌词与原文逐字相同。本次 571 字符、47 行一致，取得两个
  clip id 及 74.4s/71.56s 授权 WAV；这证明提交与下载正确，不证明歌手遵守角色分工。

### 歌声验收的 whisper 阈值坑（2026-10-17《星屑战壳》OP 实测）

- **whisper 默认 `no_speech_threshold=0.6` 会把 Suno 歌声整轨拒识成零段落**
  （或只剩"字幕by索兰娅"式幻觉串），不能据此下"纯器乐"结论。复跑须用
  `no_speech_threshold ≤0.2 + condition_on_previous_text=False`，base 模型即可
  转出与歌词逐行对应的段落。pyin 的 voiced 率在重伴奏摇滚混音里也不可靠
  （底鼓/贝斯会被判成 98Hz 男声）。
- **现行 Suno 歌曲页（v6/chirp-hawk 期）歌词面板是纯静态渲染**，无 karaoke
  逐词时间轴 DOM，`/words/`、`/aligned_words/` 等接口 404——不能用作人声判据。
  判据优先级：clip metadata `make_instrumental` + 宽松参数 whisper 复跑。

Suno **没有公开自助 API**（官方 API 仅企业定制 $499/月起）。本 skill 用
Playwright 持久化会话驱动网页版，完成 生成→下载 自动化。

## 风险与纪律（必读）

- **灰色地带**：自动化网页版违反 Suno ToS 的字面条款。仅限自己的付费账号、
  低频（每天几十首以内）、人类化节奏使用。账号有被限制的风险。
- 会话档案 `.suno_profile/` 含登录态，**必须 gitignore**，绝不提交。
- 页面改版会导致选择器失效：先跑 `--probe` 拿页面结构，校准脚本顶部
  的选择器表，再跑生成。

## 用法

```bash
cd dula-story
# 1. 首次/会话过期：自动登录（headed，凭据走环境变量；或 --login 全手动）
SUNO_EMAIL='you@gmail.com' SUNO_PASSWORD='***' \
  .venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_login.py
.venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_generate.py --login
# 2. 页面结构变了就跑探测，把 suno_probe.json 交给代理校准选择器
.venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_generate.py --probe --out tmp/
# 3. 生成（人声版 / 器乐版）
.venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_generate.py \
  --style "Chinese cinematic ballad, xun, dizi, harp, violin, warm nostalgic" \
  --lyrics-file episodes/<ep>/config/theme_lyrics.txt \
  --out episodes/<ep>/assets/audio/theme/suno/ --count 2
.venv/Scripts/python.exe ../dula-skills/suno-driver/scripts/suno_generate.py \
  --style "..." --instrumental --out ... --count 2
```

## 与其他通道的关系

- 全自动正式 API：`volc-song-gen`（火山 GenSong，经 veFaaS 中转）——优先用
- 本驱动：火山产出不符合要求（如民乐音色）时的质量上限通道
- 下载的 WAV 接入既有链路：Demucs 分离 → 对齐 → 口型（见 song-lipsync）

## 翻车记录（2026-09-26，下载链路断裂）

生成成功（clip 落库）但**下载全部失败**：`Unlock & Download` 确认后
`AttributeError` 无限重试。生成侧选择器（style/create）仍有效，下载侧
（Unlock→Download 对话框流程）已被页面改版破坏。需要跑 `--probe` 重新
校准下载选择器链；校准前片尾曲等需求走 `volc-song-gen`（GenSong v4.3
纯音乐 prompt 可用）兜底。失败截图：`suno_fail_download.png`。

## 无头模式与下载修复（2026-09-27，已验证）

- **默认无头后台运行**（`headless=True`），`--login`/`--headed` 才开窗口。
  持久会话 + cookies.json 下 Cloudflare 未拦截；脚本 goto 后检测挑战文本，
  命中会提示先 `--headed` 跑一次。
- **下载 AttributeError 根因**：`expect_download` 用法错误——先点了确认按钮
  才进入等待上下文，事件早已错过。修复为 `with page.expect_download()` 包住
  触发下载的那次点击（无确认对话框时补点 WAV 项）。无头实测下载成功（183s
  完整 WAV）。
- 待修：`instrumental` 开关选择器失效（NOT FOUND），器乐需求暂时写在
  style 文本里；title 输入框选择器同样失效（不影响生成）。

## 2026-09-28：先辨别会话失效，再诊断选择器

- `cookies.json 已注入` 只表示载入成功，不证明会话有效。实际页面若是
  `Welcome to Suno` 登录页，后续 Custom/style/title 全部 NOT FOUND 是登录问题。
- 驱动在填写之前检测登录页，保存 `suno_login_required.png`，以退出码 3 结束；
  明确未提交生成，等待用户手动 `--login`。不要反复点击或误改创作选择器。

## 2026-10-08：cookie 备份改为显式恢复（默认不注入）

- **cookie 双保险改为 opt-in**：`cookies.json` 注入现在需要显式传
  `--restore-cookies`。旧备份可能过期（实测 9 月 29 日的备份到 10 月 8 日已失效），
  自动注入会让"备份恢复"静默覆盖持久 profile 里更新的登录态，且注入成功不代表
  会话有效。默认只信持久 profile；确认 profile 损坏时才用 `--restore-cookies` 回滚。
- **每次成功进入创作页后刷新 `cookies.json`**（登录页守卫通过之后才写），
  让备份跟随最新会话滚动更新，而不是越放越旧。
- **--login 检测改为扫全部 Suno 标签页**：用户可能在脚本开的页之外的标签里完成
  登录；现在对所有 `suno.com` 标签页查创作界面元素（歌词编辑框/style 输入框/
  `My Workspace`），命中即视为已登录。
- **应急通道**：持久 profile 登录态整体过期、来不及走 `--login` 时，可改用用户
  日常已登录的浏览器手动生成/下载（如本机常驻浏览器 + WebBridge），事后补
  `.source.json` 记录 song_id 与 sha256。S1E2 R2 配乐即走此通道
  （`config/suno_score_request.json` status=downloaded）。

## 2026-10-08 晚：自动登录脚本（suno_login.py）与 Google OAuth 坑

- **Suno 没有邮箱+密码登录**：登录弹层只有 Google/Apple/Phone + Discord/
  Facebook/Microsoft。"输入邮箱密码"实际走对应 OAuth 提供方。
- **`scripts/suno_login.py`**：headed 打开 Suno → JS 按文本点 "Log in" →
  Continue with Google → 自动填邮箱/密码 → 写回持久 profile + cookies.json。
  凭据只走 `SUNO_EMAIL`/`SUNO_PASSWORD` 环境变量，不落盘。实测一次通过。
- **Google 会拒绝无头登录**：无头跑到密码步后落在
  `accounts.google.com/v3/signin/rejected`（自动化检测）；同一 profile 换
  headed（带 `--disable-blink-features=AutomationControlled`）即通过。
  登录必须 headed；登录后的生成/下载仍可无头。
- Google 表单选择器：邮箱框是 `#identifierId`（**type=text** 不是 email），
  密码框是 `input[name="Passwd"]`；导航慢，要 `wait_for_selector` 等到可见再填。
- Suno 头部 "Log in" 按钮对 `wait_for_selector`/`locator.click` 不稳定（明明
  可见却超时），直接 `page.evaluate` 按 innerText 找元素 `.click()` 可靠。

## 2026-10-11（《迟到的一拍》P3）：Voices 音频上传建档 = 账号级封锁

- **确诊**：`POST /api/persona/create/`（Bearer=抓 app 自带 studio-api 请求头）对上传 clip
  返回 **403 "Voices cannot be made from audio uploads."**——前端 JS 里对应的门是
  `personas-audio-upload` feature flag + `voices-geo` 地域门（`isAudioUploadDisabled`）。
  本机账号两样都没有。选择器怎么校准都没用，别再试。
- **上传本身能走通**（Voice 对话框 → Upload Audio → upload-finish → 选 Voice 芯片 →
  Continue → initialize-clip 200）：上传的 clip 入库可生成，只是不能建档成 Voice。
  脚本里这段流程已按 v6 校准（芯片与页面顶部 Voice 入口同文要限定对话框内点；
  Continue 未选芯片时禁用，等它没用，要先看 upload-finish 再点芯片）。
- **还能用的 Voice 路径**：从"生成出来的歌"建档 persona（persona_type='vox'，
  root_clip_id=生成 clip）——不是上传音色，是 Suno 原生声线。要角色音色一致性
  （对白 TTS 声线=歌声）的企划别走这条，走 volc-song-gen+Seed-VC 回退链。
- 副产品 API 备忘：`/api/persona/get-personas/`（GET 列表）、`/api/persona/create/`
  （POST，persona_type∈['vox','legacy']）、`/api/persona/get-persona/{id}/`；
  Bearer token 抓 app 对 studio-api-prod 的任一请求头即可（user_config 必带）。

## 环境音/配音能力实测（2026-10）

**页面结构变了**：`/create` 现在有三个模式页签 **Songs / Speech / Sounds**
（skill 既有脚本只覆盖 Songs）。Sounds 面板：描述框
`textarea[placeholder="Describe the sound you want"]`，另有 Type=One-Shot/Loop、
BPM、Key 选项，定位语是"Create short samples — effects, loops, and one-shots"。
Speech 面板：台词框 `textarea[placeholder="Write or paste your speech"]` +
演绎描述框 `textarea[placeholder="Describe the delivery: tone, pacing, mood and setting"]`
+ Male/Female 声线芯片。Songs 的 style 框 placeholder 变成动态示例文案
（如 `jolly, martial, jazz-fusion, ambient pop, 432 hz`），旧选择器表里
`Enter style tags` 已失效，`xpath=(//textarea)[2]` 仍能蒙中。

**无头 Create 被 hCaptcha 拦截（硬阻断）**：无头会话点 Create 后只有
`POST /api/c/check` 200 → `hcaptcha-endpoint-prod.suno.com/getcaptcha/...`，
**始终不发出 `/api/generate`**，约 4 分钟后页面弹 toast "Generation failed.
Something went wrong."（不是内容审核，是提交根本没发生）。同一 profile 换
**headed**（带 `--disable-blink-features=AutomationControlled`）即放行：
`POST /api/generate/v2-web/` 200，4 秒返回 2 个 clip id。结论：**生成提交必须
headed 或走常用浏览器**，无头只剩浏览/下载可用。这与 2026-10-17 条目现象一致，
此处补上了网络层根因证据。

实验设计：3 次成功提交（每次出 2 个 clip，取第一条下载），产物与分析在
`dula-story/tmp/suno_eval/`（gitignored；含 meta.json/分析 JSON/频谱图，
驱动草稿 `suno_experiment.py` 同目录）。

### 环境音（Sounds 模式）——能用，定位是"短样本"

| 产物 | prompt 要点 | 时长 | 指标 |
|------|------------|------|------|
| `amb_night_wind.wav` | 夜晚荒野：冷风过草原+远处篝火噼啪+稀疏蟋蟀，no music/no voices，Type=Loop | 12.81s | 48kHz 双声道，I=-15.8 LUFS，LRA 11.3，TPK -1.6 dBFS，RMS -17.2 dB |
| `amb_underwater.wav` | 水下：闷低频水流+慢气泡+远鲸鸣，no music/no voices，Type=Loop | 14.01s | 48kHz 双声道，I=-14.8 LUFS，LRA 12.0，TPK -1.2 dBFS，RMS -16.7 dB |

- prompt 模式：全英文声景白描 + 显式 `no music, no melody, no voices, ambient bed`。
- 频谱自查：两条都无持续谐波横线（无音乐旋律结构）；风声条全频带宽带噪声、
  低频占优；水下条能量集中在 2kHz 以下随频率滚降、高频散在竖纹（气泡状事件）。
  符合环境音底床形态。**听感本身未经人耳验收**。
- **坑 1**：UI 选 WAV、走 Unlock & Download，实际落盘文件是 **MP3 192kbps**
  （ffprobe codec=mp3，附 mjpeg 封面流）——Sounds/Speech 的"WAV"不是真 WAV，
  与 Songs 拿到的真 48k WAV 不同，接入管线前按 MP3 处理。
- **坑 2**：Type=Loop 的产物仍带淡入淡出（水下条末尾 M 落到 -45dB），
  不能直接无缝循环；长夜景底床需自行交叉淡化拼接。
- 建议用途：动画夜景/水下等短氛围底床的零成本补充来源；正式环境音主链仍是
  build-ambience-foley/Pixabay。生成耗时：提交→clip 4s，端到端（含下载）≈45s。

### 配音/说话（Speech 模式）——能产出非歌唱人声，正确性需人工试听

| 产物 | 输入 | 时长 | 指标 |
|------|------|------|------|
| `vo_epic_line.wav` | 台词「纵使长夜漫漫，吾以残躯为炬，照见黎明。」+ delivery "Male, deep low voice, slow measured epic narration, cinematic trailer gravitas, Mandarin Chinese..." | 19.20s | 48kHz 双声道，I=-17.1 LUFS，LRA 7.0，TPK -2.3 dBFS，RMS -19.9 dB |

- 频谱可见 4 个离散语音段（1.5-3.2s / 4.5-6.3s / 9.8-10.8s / 11.5-12.3s），
  低频基频强（符合低沉男声方向），段间及尾部有低电平持续底（约 -60dB），
  无歌唱式持续谐波旋律——**确实是非歌唱的 spoken word 产出**。
- 19 字台词铺成 19.2s，语速不可控、段落节奏由模型自定；台词内容逐字正确性
  **未做 ASR 验证**（本机 venv 无 whisper），需人工试听后才能入库使用。
- Male/Female 声线芯片点击未生效（选择器未命中），本次靠 delivery 文本指定
  男声；需要声线芯片时先 --probe 校准。
- 建议用途：单句史诗旁白/预告片腔可用作补充；正式角色台词仍走
  seed-tts 链（逐句可控、有 QC、声线一致性好），Suno Speech 不适合对白主力。
