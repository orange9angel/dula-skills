---
name: build-continuous-story-images
description: Plan, generate, repair, and validate character-consistent sequential story images across Imagen, Alibaba Bailian/DashScope, and other text-to-image or image-edit providers. Use for animation keyframes, motion-comic panels, storyboard sequences, action progressions, recurring characters, shot-to-shot identity locking, stable wardrobe/scene/camera continuity, or failures where separately generated frames drift in face, costume, props, direction, composition, or visual style.
---

# Build Continuous Story Images

Create a provider-neutral sequence plan, then use the strongest continuity mechanism the active provider actually supports. Preserve identity and scene state explicitly; change only the action phase intended for each shot.

## Core rules

1. **Prefer a native sequential group.** Generate one ordered action group in one request when the provider supports sequential multi-image output. Do not treat `n` unrelated samples as a sequence.
2. **Separate desired count from returned count.** Keep the narrative shot list fixed, but treat provider count and output order as advisory unless the active model explicitly guarantees them. Preserve every returned image as a candidate before assigning it to a shot.
3. **Keep master references in every fallback.** For per-shot generation, supply the approved identity reference and stable scene/style references together with the nearest approved continuity frame. Do not chain only from the previous output; accumulated drift will compound.
4. **Separate locks from deltas.** Repeat hard locks for face, hair, wardrobe, body proportions, scene, lighting, camera, style, prop count, and screen direction. Put only pose, expression, and explicitly moving props in `allowedChanges`.
5. **Plan motion before generating.** Express an action as readable phases such as setup, anticipation, action, apex/contact, and recovery. Generate neighboring phases together. For long actions, use overlapping groups whose first frame is the prior approved anchor. For cyclic locomotion, plan the full cycle, not a single alt frame — see [walk-cycles.md](references/walk-cycles.md).
6. **Approve before inheriting.** Never use a rejected or unreviewed frame as the reference for later shots.
7. **Repair locally.** Regenerate the smallest failed group or edit the faulty region. Do not replace a coherent sequence because of one recoverable hand, ball, face, or background defect.
8. **Do not use interpolation as an identity fix.** Frame interpolation can smooth timing after keyframes are correct; it cannot restore a drifting face, costume, pose path, or object trajectory.
9. **Unify the generation resolution tier.** Still images and I2V clips must be generated at the same resolution tier; a sharpness mismatch reads as a defect at every still↔video cut (uniform softness reads as style, a sudden drop reads as an error). Make the tier a switchable config, not a per-script hardcode — reference implementation: `dula-story/episodes/cat_leads_e07_river_willow/config/render_spec.json` + `tools/render_spec.sh` (exports image size + I2V resolution from one `generation_tier` value, `normalize_img()` pulls every freshly generated image to the tier size). When mixing resolutions is unavoidable, normalize all sources to the lower tier before timeline assembly and upscale once at final output.
10. **Quarantine foreshadow frames as references.** A frame containing a planted foreshadow element (a symbol, an unexplained object) must never be used as a reference image for other shots — image models copy the element into the new shot and the plant leaks early (E08 incident: the corner symbol was duplicated onto the flying page because its keyframe referenced the reveal frame). Keep a symbol-free sibling frame for reference use, and state explicitly in the prompt that the page/prop carries no symbol or ornament.
11. **Photoreal human front-faces route to OmniHuman, not I2V.** Seedance I2V platform moderation rejects photorealistic front-face first frames (`InputImageSensitiveContentDetected.PrivacyInformation`, E09 incident — no charge, but the task fails). All front-face human shots go through OmniHuman (photo + audio; a silent audio track works for non-speaking front-face shots). Anti-distortion discipline for any photoreal face: face height ≥1/4 of frame in I2V (≥1/3 in an OmniHuman base), minimal or no head motion in the prompt, hands out of frame, ≤4s per segment, and per-frame inspection of eye symmetry, gaze stability, teeth, and hairline edges before accepting the shot.

## Workflow

### 1. Inspect the narrative and references

- Read the script, storyboard, timing, and intended edit.
- Inspect every available character, wardrobe, scene, style, and prop reference.
- Identify action boundaries. Keep one continuous action and one stable camera setup per sequence unless a planned cut is part of the story.
- Choose one canonical identity reference per character. Add close-up/detail references only when they clarify a feature that the canonical image does not show.

### 2. Create the sequence plan

Run:

```bash
python scripts/init_sequence.py <project-dir> \
  --sequence-id <sequence-id> \
  --reference <character-reference.png> \
  --shot "<setup description>" \
  --shot "<anticipation description>" \
  --shot "<action description>" \
  --shot "<apex/contact description>" \
  --shot "<recovery description>"
```

Edit the resulting `config/image_sequences/<sequence-id>.json`:

- Fill every `hardLocks` category with visible, testable facts.
- Keep `allowedChanges` narrow for each shot.
- Record state before and after a moving prop when trajectory matters.
- Set provider capabilities from observed tool behavior, not assumptions.
- Mark an intentional camera change as a new group or a planned cut.

Read [continuity-contract.md](references/continuity-contract.md) when authoring or repairing a plan.

### 3. Validate and compile requests

```bash
python scripts/validate_sequence.py <sequence-plan.json> --strict
python scripts/build_generation_request.py <sequence-plan.json>
```

The compiler creates one provider-neutral generation request containing:

- a group-first prompt with ordered action phases;
- reference-image paths and hard locks;
- per-shot fallback prompts;
- a stable output mapping.
- an explicit result policy separating desired, requested, and returned counts.

Do not hand-copy prompts into multiple providers when the compiled request can remain the shared source of truth.

### 4. Select the provider path

Read [provider-adapters.md](references/provider-adapters.md) before invoking Imagen, a built-in image tool, or a new provider.

- **Sequential group + references:** submit the compiled group request once.
- **Variable or unordered group output:** save every return as an unassigned candidate, then map candidates to shots by visual action-phase review.
- **Reference edit but no sequential group:** generate the first approved frame from master references, then use master references plus the nearest approved frame for each next shot.
- **Text-only generation:** keep the same model, aspect ratio, seed when available, and full locks, but report lower confidence; create a character sheet first when possible.
- **DashScope/Bailian（按量付费；2026-08 起为 codex 配额耗尽后的 fallback，不再是主通路）:** read [dashscope-bailian.md](references/dashscope-bailian.md) and use `scripts/run_dashscope_sequence.py`. **角色 cel 局部编辑（眨眼/口型/互动中间画）只有 codex 局部编辑一条达标通路；配额耗尽就等配额，不要 fallback**——qwen-image-edit / wanx 掩码在贴回型 cel 上均已验证不合格（E02 V2–V4：喊叫嘴、半眯眼、贴回区色调漂移），qwen 全图变体只允许作为整帧独立镜头（不贴回）或废案 donor，见 [qwen-image-edit-local-cels.md](references/qwen-image-edit-local-cels.md)。

#### Lightweight single-image mode (no sequence plan)

For single artifacts that do not need the plan ceremony — style tests, character/scene
masters, one-off keyframes, and local-edit variants (mouth/eye/walk cels) — call a
lightweight adapter directly. Everything downstream (diff-lock paste-back, review
gates) is unchanged.

**Default provider: Codex built-in imagegen (gpt-image, ChatGPT subscription, zero
marginal cost)** — `scripts/gen_image_codex.py`, wraps `codex exec -i <ref>` and
harvests the product from `~/.codex/generated_images/` itself:

```bash
# single image / edit variant
python scripts/gen_image_codex.py --out <episode>/assets/keyframes/frame_00.png \
  --ref <episode>/assets/style_master.png --ref <episode>/assets/scene_room.png \
  --prompt "Use case: establishing shot ... <style hardLock> <avoid list>" \
  --size 1672x941
```

Read [codex-cli-imagegen.md](references/codex-cli-imagegen.md) first — prompt-before-`-i`
ordering, never let codex save into the project, serial foreground runs only.

**Provider 决议更新（2026-09-05 晚，导演）**：火山账户已充值，**整帧生成
（母版/关键帧/I2V）优先走火山付费**（Seedream 5.0 Pro 出图 + Seedance 2.0
满血 I2V，都在方舟，ARK_API_KEY 一把 key），codex 降级为备胎/配额补充。
**例外——编辑类变体（A/B 微动、中间帧、局部修改）仍走 codex**：Seedream
编辑会整帧重渲染（E07 实测改光斑 38% 像素变化；E04 贴回已判死），flipbook
变体要求框外逐像素一致，只有 codex 的编辑模式达标。codex 配额耗尽时的
变体兜底：用时间线 crossfade（≤0.25s）替代中间帧（E07 V4 结尾光斑实测）。

**（历史）Default chain: `scripts/gen_image_auto.py` — Codex first, DashScope
fallback（已被上方 2026-09-05 决议取代为主路，此段保留作备胎参考）.**
Codex bills against the ChatGPT subscription quota (zero marginal cost, 2026-08
用户决策：优先用 codex，配额耗尽自动切百炼）. The wrapper runs
`gen_image_codex.py` first and, only when the output matches a usage/quota/rate
limit, falls back to the paid `gen_image.py` (wan2.7-image-pro). Same interface
as `gen_image_codex.py` plus `--provider auto|codex|dashscope` and
`--dashscope-size`:

```bash
python scripts/gen_image_auto.py --out <episode>/assets/keyframes/frame_00.png \
  --ref <episode>/assets/style_master.png --ref <episode>/assets/scene_room.png \
  --prompt "Use case: establishing shot ... <style hardLock> <avoid list>" \
  --size 1672x941
```

**Fallback provider: DashScope/Bailian (`scripts/gen_image.py`, wan2.7-image-pro)** —
按量付费。Only reached automatically on codex quota exhaustion (via
`gen_image_auto.py`), or directly when structured API knobs (seed, mask,
negative prompt) are truly required. `scripts/gen_batch.py` drives the DashScope
path directly (paid every call); for batches, run `gen_image_auto.py` serially
from a shell loop.

**图生视频（`scripts/gen_i2v.py`, wan2.6-i2v-flash）** — 连续动作镜头（走路/跑跳）
的首选用法：先用本 skill 生成该镜头的首帧关键帧，再
`gen_i2v.py --first-frame <kf> --duration 3 --resolution 720P --extract-cels <dir>`
产出 3s 无声视频并抽 12fps cel 铺进时间线（`move: static`）。成本 ¥0.15/s ≈
¥0.45/条（720P 无声）。首帧构图必须给动作留空间（角色放画面左 1/3、面向右、
前方留空），prompt 明说镜头固定/风格锁定/不加新元素。选型细节与验收见
[walk-director/references/keyframe-walk-shots.md](../../walk-director/references/keyframe-walk-shots.md)
「选型」节。

**I2V 选型结论（2026-08-29，cat_leads_e03_dusk_homecoming 实测）**：
- flash 档（¥0.15/s）：动作生动但快速动作会轻微 off-model
- 标准档（¥0.6/s）：一致性够但**动作量保守**（人物并腿滑行，E03 V1 翻车点）
- seedance 2.0 的 `--ref` 多图参考可锁身份，但与 `--first-frame` 互斥，
  首帧连续性优先的场景仍用首帧模式

**I2V 选型更新（2026-09-05，cat_leads_e05_morning_sketch 实测）**：
- **正片用满血版 `doubao-seedance-2-0-260128` @1080p**（~¥0.99/s，4s ≈¥1.6/条）：
  输出 1920×1080 ≥ 关键帧 1672×941，剪辑点零放大；E04 用 mini 720p 被放大
  1.5× 产生的虚边在 E05 消失。3 段一次通过，身份/风格保持好。
- **mini（720p，~¥0.5/s）降级为打样/试镜档**：prompt 调参阶段用 mini 快速
  验证动作量，定稿后用满血版重跑同 prompt 同首帧。
- 次级动态（裙摆/发丝/草浪/尾巴）写法与风力分级见
  [references/i2v-motion-details.md](references/i2v-motion-details.md)。
  **注意该文「I2V 语法边界」一节（E05 导演复片后立）**：布料/发丝特写、
  表情变化镜头不要用 I2V（布条形变感），回关键帧姿势变体语法；I2V 只用于
  全身位移、运镜、大环境运动三类。

**图生视频 Seedance 变体（`scripts/gen_i2v_seedance.py`, 火山方舟）** — 当
wan2.6 系在快速动作中出现角色漂移或动作量不足时的对照/升级通路。CLI 与
`gen_i2v.py` 一致，可同首帧同 prompt 直接 A/B。需要 `ARK_API_KEY`（开通有
¥200 余额门槛，后付费按量计费，开通本身免费）。默认
`doubao-seedance-2-0-260128`（~¥0.99/s 720p，4-15s，支持 `--ref` 多图参考锁
身份，与 `--first-frame` 互斥；2.x 记得无声要显式 `generate_audio=false`，
脚本已处理）；便宜档 `doubao-seedance-2-0-mini-260615`（~¥0.50/s；**必须带
日期后缀**，裸写 `doubao-seedance-2-0-mini` 方舟报 404 NotFound——E04
（2026-08-29）实测踩坑）；1.0 pro
（~¥0.32/s，最短 5s，支持 `--camera-fixed`）。注意：E03（2026-08-29）实测百炼两档都不够（flash 漂移、标准档滑行），
**seedance 2.0 mini 4 段一次通过成为正片采用方案**；`.env.ark` 放
dula-story 根目录（已 gitignore），`set -a && source .env.ark` 后用。

Reference order is weight order: identity master first, nearest approved frame next.
Edit variants are the same call with only the base frame as `--ref` and an instruction
prompt ("change only the mouth to half-open"); still diff-check and feather-lock the
result back onto the base frame with the episode's existing tools. Run batches
serially and review each frame before it becomes the next frame's reference. Use the
full sequence plan instead whenever shots form an action-phase group.

**表演密度（2026-08-15 snow_fox_shrine 复盘）**：只有口型+眨眼两个通道的静帧
剧集会显得"表情变化少、动作少"。在像素锁定纪律内可以低成本加戏，全部走
局部编辑 + 锁区贴回：

- **表情变体**：同一基帧加做一张情绪局部变体（闭眼微笑、眯眼笑），镜头
  中段硬切一次；
- **反应变体**：动物/角色的耳朵竖起、尾巴拍地等小幅局部变体，在故事节拍点
  （钟声、被叫名字）切入；
- **姿态中间画**：蹲下↔起身这类大姿态切换加一张 in-between（参考 cat_leads
  的 crouch_mid）；
- **镜头内二次构图**：长镜头中段切一次更近的取景（新画一张，不要只改 crop）。

这些不是 A/B 连续动作（walk-director 的锁定红线不适用），因为每张变体在
时间线上只出现一次、不构成高频交替。

Never claim a capability because another model from the same vendor supports it.

### 5. Review as a sequence

Inspect both individual frames and a chronological contact sheet. Check:

- face shape, eye color, hair silhouette, accessories, body proportions;
- wardrobe geometry, colors, numbers/logos, and left/right placement;
- character count, limb count, prop count, and hand-object contact;
- background layout, light direction, camera height, focal scale, and horizon;
- screen direction, foot placement, body balance, action progression, and prop trajectory;
- whether adjacent frames show actual motion rather than unrelated poses;
- whether frames intended as opposite action phases actually differ in phase — name the concrete phase marker (e.g. which leg is forward, which arm is raised) and verify it swapped. A "walk alt" that copies the reference's leg assignment is a reject, even when composition and identity are perfect. Do not accept an in-between merely because it exists in the timeline;
- for walk cycles, prefer contact ↔ passing-pose alternation over contact ↔ opposite-contact. Models anchored on a contact-pose reference tend to twist shoe orientation when forced into the opposite contact (backwards-looking feet), and the failure survives phase-marker review. In a passing pose the lifted foot hangs with the toe pointing down, which models render reliably. Whichever pose is used, verify shoe/toe direction against the direction of travel, not just which leg leads.

Do not assign by array index when output order is unconfirmed. If the provider returns fewer images than planned, assign the valid candidates first and generate only missing shots. If it returns more, retain the surplus as unassigned alternatives until review is complete.

Register images produced by a tool that does not write the plan directly:

```bash
python scripts/register_candidates.py <sequence-plan.json> \
  --provider imagen --requested-count 5 \
  --output <returned-image-1.png> --output <returned-image-2.png>
```

Record `accepted`, `rejected`, or `needs_repair` in the plan only after visual review. Preserve the provider/model, request, task/run identifier, seed when exposed, reference set, and output path needed to reproduce the decision.

Record each decision explicitly:

```bash
python scripts/review_sequence.py <sequence-plan.json> \
  --shot shot_01 --status accepted --output <reviewed-frame.png> \
  --clear-issues --notes "<what was checked>"
```

### 6. Repair and finish

- Repair a local anatomy or prop defect with image editing when the rest of the frame is sound.
- Regenerate a short overlapping group when motion continuity fails across multiple shots.
- Split at an editorial cut when the camera must change materially.
- After all keyframes pass, perform interpolation or video generation as a separate downstream step.

Run final validation:

```bash
python scripts/validate_sequence.py <sequence-plan.json> --final --strict
```

## Acceptance bar

- Every planned shot has exactly one approved output.
- No approved frame inherits from a rejected frame.
- Hard locks remain visibly stable unless the story explicitly changes them.
- Action phases advance causally and preserve screen direction.
- Prop positions form a plausible trajectory.
- Provider limitations and any unresolved low-confidence details are stated plainly.

**E04 V1.1 追加教训（2026-08-30）**：Seedream 变体若用整脸框贴回，rig 矩形会被
框内重渲染噪点撑大，导致 cel 切换时整块脸抖动。**贴回框必须收紧到特征本身**
（嘴/眼小矩形）；自动致密 diff（t=60 + 3x3 腐蚀）对少女脸有效，猫毛纹理和大
特写仍需手工标定。参照 `cat_leads_e04_firefly_night/tools/relock_tight.py`。

**E04 终局（2026-08-30）：贴回型 cel 口型工艺整体退役**。说话镜头改用
OmniHuman 1.5 对口型视频（音频驱动、口型天然同步、免费试用）——接入与纪律见
`../build-character-voice/references/volcano-omnihuman.md`。codex 局部编辑仍保留
为眨眼/非说话微调的首选通路；qwen/wanx/seedream 贴回全部判死（几何漂移 2-6px
实测，E04 tools/diagnose_align.py）。

**路线决议（2026-09-05）：不做风格/角色 LoRA**。评估过把晴印风格烙进模型权重
（云 4090 训 Flux LoRA，单次 ¥10-30，本机无 GPU），导演决定搁置：一致性走
"参考图锁定 + prompt 纪律 + 关键帧质量验收"路线，赌基础模型持续变强。
LoRA 的固有问题：gpt-image 闭源不可微调，换 Flux 底模构图/指令遵循可能降档；
且 Flux.1-dev 非商用许可。若未来集数上量、一致性返工成本明显，可重开此评估
（训练集现成：E04-E06 精选 30-50 张）。
