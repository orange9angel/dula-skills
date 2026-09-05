# 火山即梦 OmniHuman 1.5 对口型接入备忘（说话镜头工艺）

> 来源：2026-08-30 E04《夏夜流萤》实测接入并转正。用途：**说话镜头用
> 「图 + 音频 → 口型同步视频」取代贴回型口型 cel**。E02–E04 三集验证：
> qwen/wanx/seedream 的贴回变体全部不达标（几何漂移/质感沸腾），codex 达标但
> 被 OmniHuman 全面取代（音频驱动口型天然同步、自带微表情、免费试用额度）。

## 鉴权与服务开通

- 产品线：**即梦 AI**（火山引擎控制台独立产品线，不是方舟、不是语音控制台）。
- 开通：console.volcengine.com/jimeng → 开通 OmniHuman1.5（有免费试用，1 并发）。
- 密钥：**IAM 子用户 AK/SK**（console.volcengine.com/iam/keymanage/）——
  建议建子用户（如 dula-api）只挂 `CVFullAccess` + `TOSFullAccess` 两条系统策略，
  别用主账号 key。存 `dula-story/.env.cv`（gitignore）：VOLC_ACCESSKEY/VOLC_SECRETKEY。
- API 形态：任务式 `CVSubmitTask` → `CVGetResult` 轮询，Region cn-north-1，
  Service cv，req_key=`jimeng_realman_avatar_picture_omni_v15`。
  官方 SDK `volcengine`（pip）的 `VisualService.cv_submit_task(form)` 直接可用。
- 音频入参上限 60s（建议 <15s）；输出 720P/1080P mp4；RTF≈23-27（2s 片段约 1-2 分钟）。

## 最大的坑：图片和音频必须是公网 URL

- `image_url` / `audio_url` **只接受公网 URL**，服务端抓取。
- base64 字段（image_base64/audio_base64）：提交返回成功但任务校验失败
  （查询报 50215 Input invalid）——字段被静默忽略，**不要信提交成功**。
- data: URI：50220 Download Url Error。
- 海外临时图床（tmpfiles.org 等）：火山国内机房拉取被 reset，死路。
- **正解：TOS 对象存储**——开通 TOS（存储量计费，试点量级每月几分钱），
  上传后出预签名 GET URL（2h 有效，够服务端抓取）。E04 工具：
  `tools/tos_upload.py`（自动建私有桶 `dula-e04-omnihuman-assets`）。

## 生产纪律（E04 验收教训）

1. **姿态锁定必须写进 prompt**："保持姿势和位置完全不动，只有嘴部随说话开合"——
   不写模型会自己加戏（实测猫从站姿自作主张改成坐姿，前后镜头断戏）。
2. **垫帧垫前面，不垫末尾**：视频从 0 秒就带口型，而台词往往在镜头开始
   0.1-1.4s 后才起。按台词在镜头内的 lead 偏移**前垫**静止首帧、末尾不够再
   垫末帧（E04 tools/gen_omni_shots.py）。垫反了就是"第 6 秒猫说话不同步"。
3. **逐段抽帧查肢体数**：行走+说话的组合 prompt 容易 hallucinate（实测出
   三只手）。修复先改 prompt（显式"双臂自然下垂贴身"），再换 seed。
3b. **标志性手势会被"放松"掉（E05 实测）**：底图里的独特姿势（如抬手挠头）
   在视频段落中可能被 OmniHuman 中性化回普通姿态——它保表情和口型，不保
   手势。关键手势要么安排在相邻静态帧里呈现，要么接受丢失；验收时除查
   肢体数外还要查"底图手势是否存活"。
3c. **神态分层 prompt 有效（E05 实测）**：在姿态锁定句之外加"视线方向+
   眉部微动作+呼吸感"（如"视线先躲闪下移再抬回""下巴微抬、眼睛半眯"），
   一次到位率明显高于只写"神情XX"整词。
4. **分辨率直接用 1080P**：720P 快档放在 1080P 静帧旁边明显软（pe_fast_mode
  按官方建议：720→true、1080→false）。视频模型单帧天生比静帧软，源头给足
  分辨率是唯一有效手段。
5. **槽位边界逐对对齐**：omni cel 序列的槽尾必须等于下一静态帧的 at，
   交叠 0.1s 就会在边界闪切（"画面抖了一下"）。
6. 视频自带音轨剥离不用——混音仍用剧集 mixed.wav，同步由"音频即驱动源"保证。

## E04 工具链（可直接复用）

- `tools/omnihuman_gen.py`：单条提交+轮询+下载。
- `tools/tos_upload.py`：TOS 上传 + 预签名 URL。
- `tools/gen_omni_shots.py`：批量（台词表驱动：shot/关键帧/音频/槽长/lead/prompt），
  抽 12fps cel + 前垫后垫，产物 `assets/omni/<shot>/f_*.png`。
- `tools/build_timeline.py --mode omni|cel`：omni 模式用 cel 序列替换说话镜头，
  cel 模式回退到 rig 静态帧（对照组/降级）。
