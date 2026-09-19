---
name: volc-song-gen
description: 火山豆包音乐模型（imagination/GenSongForTime）生成带人声歌曲 —— 含海外 IP 限制（ServerIpLimit）的 veFaaS 云函数中转方案、后付费计费、参数枚举与翻车记录。需要"AI 唱歌/歌词成曲"时使用。
---

# Volc Song Gen（豆包音乐模型 · 人声歌曲生成）

火山引擎「AI 音乐生成大模型」（产品文档树：`音视频理解与处理`，doc 84992），
输入歌词或提示词，输出**带人声的完整歌曲**。参考实现：
`dula-story/episodes/yuki_beat_ad/tools/song_gen.py`（本地入口）+
`tools/vefaas_song_relay.py`（云端中转）。

## 关键事实

- **接口**：`POST https://open.volcengineapi.com/?Action=GenSongForTime&Version=2024-08-12`
  （后付费/按时长），查询任务 `Action=QuerySong`；Service=`imagination`，Region=`cn-beijing`。
  预付费套餐包是另一个 Action（`GenSongV4`），不要混用。
- **计费**：按时长后付费 **0.002 元/秒**（30s ≈ 0.06 元），30–240s/首，QPS ≤ 2。
  资源包（万元级）只有大量产才划算，个人/单集永远选后付费。
- **开通**：主账号在 [AI音乐生成控制台](https://console.volcengine.com/ai-music/product)
  手动开通"按时长付费"；子账号调用需授 **ImaginationFullAccess**
  （该产品挂在"智能美化特效（Imagination）"服务域下，名字像图像产品但管的就是音乐）。
- **模型版本**：v4.0（默认）/ v4.3 / v5.0。Genre/Mood/Gender/Timbre/Tempo 等
  控制参数仅 v4.x 生效，**v5.0 全部忽略**。

## 翻车记录（全是实测踩出来的）

1. **ServerIpLimit（100011）= 海外 IP 限制使用**。与白名单/IAM 策略无关，
   是产品侧地域限制（内置歌词版权风控，仅服务国内）。解法见下节 veFaaS 中转。
2. **Mood/Genre 等枚举只接受英文枚举值**（如 `Cute/Playful`、`Happy`），
   传中文报 100010 InvalidRequestParams，错误信息里带完整枚举列表。
3. **QuerySong 任务 ID 参数名是 `TaskID`**（大写 ID），且绑定在 **URL query**
   而非 JSON body。relay 里实现了 4 种命名 × POST query/POST body/GET query
   的自动尝试。
4. **veFaaS 代码上传后要"发布"才生效**——只保存不发布，触发器调用的还是旧版。
   排障时给函数加版本标记字段（如 `"rv": "rv4"`）随响应返回，先验证版本再调试。
5. veFaaS 的"安装依赖"按钮要求包里有 `requirements.txt`，零依赖函数也要放一个
   空的，否则构建报 400。
6. API 最短时长 30s，**不能生成 13s 这种广告短片长度**；短于 30s 的需求用
   30s 生成后裁剪。

## 海外调用的 veFaaS 中转方案

函数出口 IP 天然国内。部署：`tools/vefaas_song_relay.py`（纯标准库，手写火山
V4 签名，与 volcengine SDK SignerV4 逐字节对齐，Python 3.9+ 零依赖）。

1. veFaaS 控制台创建**事件函数**（Python 3.12，国内地域，超时 **600s**，
   最小规格 0.25 vCPU / 0.5 GiB，保持"默认网卡访问公网"启用）
2. 代码包上传 zip（内含 `index.py` + 空 `requirements.txt`）
3. 环境变量：`VOLC_ACCESSKEY` / `VOLC_SECRETKEY`（子账号 AK/SK）+
   `RELAY_TOKEN`（自造防蹭令牌）
4. 触发器：选 **API 网关**（veFaaS 的 HTTP 入口就是它），**Serverless 网关**
   + 公网 + 无认证 + 网关超时拉满；实例初始化约 1-3 分钟，"运行中"才能绑触发器
5. 本地 `.env.speech` 配 `SONG_RELAY_URL` / `SONG_RELAY_TOKEN`，
   `song_gen.py --via-relay` 即可，音频 base64 回传（避免音频 URL 再遇地域限制）

## 用法（以 yuki_beat_ad 为例）

```powershell
cd dula-story
.venv\Scripts\python.exe episodes\yuki_beat_ad\tools\song_gen.py --via-relay \
  --lyrics-file episodes\yuki_beat_ad\config\diva_lyrics.txt \
  --genre Pop --mood "Cute/Playful" --gender Female --duration 30 \
  --out episodes\yuki_beat_ad\assets\audio\music\song.wav
```

## 已知局限（接入卡点/口型链路时注意）

接入唱跳视频、修复口型或舞蹈配合时，阅读
[唱跳表演与验收记录](references/singing-performance.md)：人声分离、已知歌词对齐、
视素近似、完整乐句编舞，以及 V8/V9 误判与 V10 修正的验证边界。

- 成曲节奏与画面"同一拍网"需要对齐策略：要么生成时用 v4.3 `Tempo` 锁 BPM，
  要么编排侧按成曲检测点重排（yuki_beat_ad V8 已知问题 1）
- 口型同步若用能量包络，背景音乐泄漏会导致开合点漂移；最好分离人声后再提取
  （yuki_beat_ad V8 已知问题 2）

## 纯音乐/卡点编曲：多候选 + 客观指标选版

不要"生成一首就用"。卡点广告类短片的经验做法（yuki_beat_ad V7）：

1. 同一 prompt 族生成 3-5 个候选（Seed-Audio 或 GenSong 纯音乐均可）
2. 用客观指标机选：重音数量与位置、drop 点时间、抽空 gap、低频占比、
   高频点缀密度——卡点片的关键是**重音结构**，不是"好听"
3. 盲听/评审模型只做 advisory，最终留一版可复跑的客观记录
4. 选定后再进锁拍/母带链（参考 `prepare_v5.py` 的 <150Hz 底鼓锁拍 +
   压缩/低搁架/限制器母带）

## 能力边界（2026-09-19 实测）

- **没有真民乐音色**：埙/竹笛/尺八等不存在于乐器枚举（Flute/Strings/Keys 等
  西洋乐器），Lyrics/Prompt/纯音乐三条路线实测均产出流行/合成音色。
  自由文本 Prompt 写"埙独奏开场"也无效。需要真民乐味就走混合制作：
  真采样（Freesound 预览可免登录抓取）定调 + AI 垫底。
- **纯音乐后付费接口名是 `GenBGMForTime`**（文档只写了预付 GenBGM，
  预付接口会报 APINoSource 200028）。
- 参数枚举都要英文：Mood（Happy/Cute\Playful...）、Timbre（Gentle/Delicate...）、
  Tempo 用意大利速度术语（Adagio/Andante/Vivace...）、Instrument 英文枚举
  （Acoustic_Piano/Synthesizers/Drums...）。传中文报 100010，错误信息附完整枚举表。
- 音频 CDN（douyinvod.com）**不受地域限制**——只有 API 调用受 ServerIpLimit，
  拿到 URL 后海外直接下载即可，无需 base64 回传。

## 盲听评审（qwen3-omni）的可信度上限

`theme_listen_review.py`（E08）把音频送 qwen3-omni-flash 盲听。实测：它能正确
识别乐器真假、调性冲突、断裂点，但**音色品味判断不可靠**——它评价"哀而不伤
成立"的埙采样被监制判为"像哀乐"。只用它做粗筛（排除明显错误），不做定稿依据。
