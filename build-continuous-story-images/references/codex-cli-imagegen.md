# Codex CLI built-in imagegen adapter（2026-07 验证）

当环境里装有 Codex CLI（已登录 ChatGPT 订阅）时，可把它当作零边际成本的图像生成/编辑 provider。
首次完整验证：`dula-story/episodes/rainy_rooftop_cat`（31 秒日漫短片，2 张角色母版 + 18 张关键帧 + 6 张嘴部局部编辑，全部一次通过）。

## 调用形态

```bash
codex exec "<prompt>" --skip-git-repo-check --ephemeral -s workspace-write \
  -i <ref1.png> -i <ref2.png>
```

## 已验证能力与坑

- `-i/--image` 是**可变参数**：把 prompt 作为位置参数放在 `-i` 之前，或 prompt 走 stdin；否则 prompt 会被吞成“文件”，报 `No prompt provided via stdin`。
- 只读沙箱（默认）下 agent 无法把图保存到项目目录：加 `-s workspace-write`。
- 成品落在哪由 prompt 里给的绝对路径决定；不给路径时原始输出在 `~/.codex/generated_images/<uuid>/call_*.png`。
- 输出尺寸约 1672×941（偶发 1664×936 / 1672×938），近 16:9；渲染侧 cover-crop 适配即可。
- 多参考图：母版（身份锁）+ 紧邻前一帧（构图连续）+ 构图参照，图序即权重序，在 prompt 里注明「image 1 = identity, image 2 = staging, image 3 = composition only」。
- **局部编辑（嘴部变体）可用且稳定**：指示“只改嘴部为 half-open/open，其余像素不变”，实测差异 confined 在嘴部小矩形（60–830 像素，<0.06%），其余像素零变化。适合做 lipsync image-mode rig 的 half/open 变体；生成后仍需像素 diff 校验 + 羽化贴回基帧（模板 `lock_mouth_variant.py`）。
- **局部编辑同样适用于眨眼变体**（rainy_rooftop_cat V3 验证，7 张）：指示“只把双眼改成闭合，其余像素不变”，产物按 mouth 变体同一流程羽化锁定。eye rig 的 rect 可以从 base↔variant 的像素 diff bbox + margin 直接得到。
  - 闭眼弧线必须在 prompt 里叮嘱「极细、浅色、短弧线，不要粗黑厚眼线」（cat_leads_e01 V10→V12 两轮教训）：模型默认给浓重弧线，闭眼帧会读出「眼睛肿了」。
- **prompt 里的输出尺寸必须等于该基帧的真实尺寸**：同一剧集的不同关键帧尺寸可能不同（实测同集混有 1672×941 / 1664×936 / 1672×938）。批量脚本若硬编码统一尺寸，尺寸不符的帧会被 agent 整体重渲染，构图偏移几十像素、局部编辑失败。逐帧先 `ffprobe`/PIL 确认尺寸再写进 prompt。
- **不要让 codex 把成品保存到项目绝对路径**（Windows 实测翻车）：其保存步骤会走 PowerShell `Add-Type` 内嵌 C# 合成，可能编译失败导致文件不落盘。改为生成后从 `~/.codex/generated_images/<session-id>/` 自行回收——文件名可能是 `call_*.png` 或 `exec-*.png`，session id 从 `codex exec` stdout 的 `session id:` 行抓取。
  - 反例（2026-08 cat_leads_e01）：该集 V1–V12 全部口型/眨眼/走路变体均由 codex 直存项目绝对路径成功（`--ephemeral -s workspace-write`，含闭眼 v4 单发）。翻车可能与环境有关；直存失败时再退到回收路径。
- **agent 会自选输出文件名，且串行批量时不同 run 可能互相覆盖**（实测 half 变体先写成 `frame_06_mouth_open.png`，后续 open run 又写同名文件）。每个 run 结束后立即按日志验收并归档到规范命名，再跑下一个。
- **羽化锁定工具的 rect 必须给足羽化余量**：`lock_mouth_variant.py` 的羽化区从 rect 边缘向内延伸约 `inset + 2×feather`（feather=14 时 ≈46px）。目标特征（眼睛/嘴）若贴 rect 边缘，会被羽化混回基帧内容（实测猫眼变“半睁”）。rect 每边至少留 40–50px 余量，锁定后必须全分辨率目检特征本身，不能只看 diff bbox。
- 连续性纪律沿用 continuity-contract.md：design lock 逐字写死、共享锁文本每帧追加、逐张目检、废帧记录原因后局部纠偏。
- 每张耗时约 1–2 分钟；**不要用 Kimi 的后台任务并行派发多个 codex exec 生图后放任不管**——子代理 turn 结束时其后台进程会被回收，任务无声丢失（本片因此丢过 4 张变体）。串行前台执行，或自己用 shell 脚本批量。
- 费用走 ChatGPT 订阅配额，不计 API 现金；大量生图时注意订阅侧的速率限制。

## 2026-08 走路循环中间帧批量生成（13 张）新教训

- **多行 prompt 会丢 `-i` 附件**：Windows 下脚本走 `cmd /c codex.CMD exec <prompt> ... -i <图>`，prompt 内含换行时 cmd 解析截断，codex 报 `requested the last 1 conversation images, but only 0 were available`。prompt 文件必须扁平成单行。扁平后仍有**间歇性**附件丢失（约 1/4 概率，同样的命令重试即恢复），失败约 1 分钟内快速返回，直接重试即可。
- **agent 会在一个 session 内自我迭代生成多张候选**（实测单 run 产 3–4 张 exec-*.png，各相隔 2–3 分钟），导致单次 run 超过脚本 `--timeout` 被 subprocess 强杀、产物不回收。对策：超时后去 `~/.codex/generated_images/<最新 session>/` 手动回收，最新一张通常是 agent 的最终候选，验收后按规范命名归档即可，不算额外 roll。prompt 里加 "Generate exactly one image." 收效甚微。
- **Kimi 后台任务仍会被静默回收**：超过前台 300s 上限的 codex run 被转入后台后，曾出现进程消失、任务状态卡在 running 直到超时的情况。可用模式：后台任务跑 codex + 前台 sleep 轮询产物文件保持 turn 存活；失败/超时则 harvest session 目录。
- **背面视角 down/recoil 相位极易锚定失败**：以 contact2 为 ref 生成 down2 时，模型两次把前后腿画反（沿用接触 A 的腿序）或收成并腿。对策：prompt 里用 viewer 视角逐字描述参考图的脚位（"viewer 右侧的鞋在画面中更高=在前"），第三次成功。

## 何时不用它

- 需要精确 seed/negative prompt/mask API 等结构化参数时——它没有这些旋钮，一切靠自然语言。
- 需要程序化批量（>30 张）且要求失败可重试的流水线时——自然语言 agent 回路不如直连 API 可控，建议走 dashscope-bailian.md 的适配器。

## 2026-08 xiaoju_secret 补充：局部编辑的两种失败与对策

- **整图局部编辑可能静默漂移**（"只改嘴部其余不变"失效）：同一批 41 个变体中约半数被整体
  重渲染（diff bbox 覆盖全图）。对策是**裁剪强制局部编辑**：裁出特征区单独送编辑、再羽化
  贴回，局部性由构造保证；且贴回必须只贴特征小 rect，整张贴回会在 cel 切换时闪（矩形内
  重绘噪声）。完整流程见 qwen-image-edit-local-cels.md（对 codex/qwen 均适用）。
- **配额锁定时的替代**：codex 报 `usage limit` 后按提示日期恢复；期间用 qwen-image-edit
  （百炼按量付费）做角色 cel 编辑，本体保持同级别，见上述参考。
