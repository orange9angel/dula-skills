---
name: motion-transfer-video
description: Make a subject image (cat, blobfish, mascot, product character) perform the motion of a reference video — the "抖音猫咪跳舞" genre — using Douyin source download plus Volcano Ark Seedance 2.0 multi-modal reference. Use for dance/motion transfer memes, mascot videos, or any "X does what this video does" content.
---

# Motion Transfer Video（动作迁移短视频）

抖音"美女跳舞→猫咪跳舞"那一类的完整链路：素材下载 → 角色图 → 动作迁移 → 合音乐。

## 管线

0. **找素材（可选，需登录）**：`scripts/search_douyin.py "<关键词>" --limit 20 --sort likes --out result.json`
   抖音 UI 搜索（匿名搜索全被墙，见翻车记录）。首次运行 headed 起真 Chrome
   停在登录页，**需手机扫码登录**（5 分钟超时）；登录态存到独立工作 profile
   `motion-transfer-video/.chrome-profile/`（不碰用户真实 Chrome profile，
   已 gitignore），后续运行 headless 直接搜。加 `--download <目录>` 可对结果
   逐条走 download_douyin.py 的 cookie jar + yt-dlp 链路下载。
   冒烟自检：`search_douyin.py --smoke`（headed 开首页报登录态，窗口停 30s）。
1. **素材下载**：`scripts/download_douyin.py "<分享链接>" -o out.mp4`
   （抖音网页无登录态不下发视频流；脚本自动复制 Chrome 最小 profile +
   无头真 Chrome 取 cookie + MozillaCookieJar 喂 yt-dlp。详见下方翻车记录。）
2. **角色图**：seedream 出一张直立全身角色图（方舟 `images/generations`，
   `doubao-seedream-5-0-pro-260628`，¥0.3/张）。要点：**直立、全身、
   纯色背景、竖屏**——越像人形站姿，动作迁移越准。
3. **动作迁移**：`scripts/gen_motion_transfer.py --image <角色图> 
   --video-url <公网URL> --prompt "<迁移指令>" --out out.mp4`
4. **合音乐**：模型不保留原曲，生成时用无声，事后免费合回：
   `ffmpeg -i out.mp4 -i source.mp4 -map 0:v -map 1:a -c:v copy -c:a aac -shortest final.mp4`

## 翻车记录（2026-08-29 实测）

- **抖音 cookie**：Chrome ≥127 的 cookie 是 v20 app-bound 加密，只有 Chrome
  自己能解；直接读数据库 / yt-dlp `--cookies-from-browser` 全部失败。
  可用路径：复制 `Local State` + `Default/Network/Cookies` 到临时目录，
  playwright `launch_persistent_context(channel="chrome")` 起**真 Chrome**
  无头读 cookie（CDP 或直接 `.cookies()` 都行）。注意：①浏览器必须完全退出
  否则 Cookies 文件被锁；②直接用原始 profile 目录起 CDP 会被 Chrome 拒
  （"DevTools remote debugging requires a non-default data directory"），
  必须复制；③手写 Netscape cookies.txt 容易被 yt-dlp 拒（负数 expires 等），
  用 `MozillaCookieJar.save()` 生成。
- **yt-dlp 对抖音分享链接本身的提取器已坏**（2026-03 版，报 "Failed to parse
  JSON"），但有新鲜 cookie 就能过——它走的是网页端点。
- **reference_video 只收公网 URL**（base64 被拒）；reference_image 可以 base64。
  公网托管 catbox.moe 可用（匿名、不可删，等自然过期）；0x0.st 已关，
  tmpfiles.org DNS 不通。
- **mini 够用好笑内容**：2.0 mini 与标准版迁移质量观感无差（meme 场景），
  价格 ¥14/M vs ¥31/M tokens，出片快 5 倍。精细内容再上标准版。
- **合规**：别人视频当动作源只迁移运动学数据（成品里没有人），自己玩可以；
  要发布/商用就自己拍动作源。不要进火山真人素材库（要扫脸认证）。
- **匿名"发现"全被墙**（2026-08-30 实测）：`/search/<kw>` 弹「登录后即可搜索」
  无关闭按钮、0 搜索 XHR；`challenge/search` 返 2483「请先登录」；
  `challenge/aweme` 匿名 200 但空 body；话题页渲染出的视频链接是随机推荐。
  匿名唯一可用的是 `/htmlmap/hotchallenge_<0-19>_1` SEO 话题榜（每页 200 条，
  只覆盖头部话题）。**拿素材只能靠分享链接**：手机 App 分享 →
  `download_douyin.py`；或先退出 Chrome 扫码登录网页抖音再自动搜。
  外部搜索引擎（Bing/百度/搜狗/360/头条API）均不收录或反爬，补不了。
  下载链路本身（视频详情页 + cookies jar）匿名可用，jar 隔天仍有效。
- **登录态 UI 搜索**（2026-09-15 实装）：`scripts/search_douyin.py` 用
  playwright `launch_persistent_context(channel="chrome")` 起真 Chrome，
  user_data_dir 用仓库内独立工作 profile `.chrome-profile/`（已 gitignore；
  **不复制也不碰用户真实 Chrome profile**，避开 Cookies 文件锁和 CDP 拒
  default 目录两个坑）。登录判定 = cookie 里有 `sessionid`/`sessionid_ss`，
  DOM 兜底（头像容器在 / 顶栏无"登录"按钮）。首次运行 headed 开首页 → 点
  "登录"出二维码 → 轮询 5 分钟等扫码 → 存 storage_state；之后 headless 优
  先、取到 0 条或撞登录墙再回落 headed。搜索页 `www.douyin.com/search/<kw>
  ?type=video`，`--sort likes` 点"最多点赞"筛选；结果从 `/video/<id>` 锚点
  卡片 DOM 提 aweme id/标题/作者/点赞/时长，滚动分批 + 1.5–4s 随机 sleep
  防风控。`--download` 复用 `download_douyin.build_cookie_jar`（拿工作
  profile 直接出 jar）+ yt-dlp 逐条下载。
- **免 profile 复制的匿名 jar**（2026-09-12 实测）：Chrome 正在运行时
  profile 复制链路（Cookies 文件锁）会拿到不新鲜 cookie，yt-dlp 报
  "Fresh cookies needed"。更轻的替代：playwright 全新 chromium 上下文
  （不用用户 profile）直接 `goto` 视频详情页，页面加载即下发反爬 cookie，
  `ctx.cookies()` 存 MozillaCookieJar 喂 yt-dlp 即过——无需退出 Chrome、
  无需登录。B 站 412 风控同理但匿名 jar 不够（要登录态 cookie）。
- **B 站/新片场参考片抓取**（2026-09-12 实测）：yt-dlp 裸抓 B 站 412、
  新片场 403；playwright 真浏览器 + 响应嗅探也拿不到新片场视频流。
  参考片首选抖音分享链接。

## 成本参考

| 项 | 价格 |
|----|------|
| 角色图（seedream 5.0 pro） | ¥0.3/张 |
| 动作迁移 5s/720p（mini，含视频输入） | ≈¥5.2（4 折期 ≈¥2.1） |
| 同上（标准版） | ≈¥11.4 |
| 合音乐 | 0 |
