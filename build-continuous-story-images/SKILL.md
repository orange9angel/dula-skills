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
- **DashScope/Bailian（按量付费，2026-08 起默认停用，用前须先确认费用）:** read [dashscope-bailian.md](references/dashscope-bailian.md) and use `scripts/run_dashscope_sequence.py`.

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

**Suspended: DashScope/Bailian (`scripts/gen_image.py`, wan2.7-image-pro)** — 按量付费，
2026-08 用户决定停用（一次走路 cel 批量约 ¥8）。Only use when structured API knobs
(seed, mask, negative prompt) are truly required, and confirm cost with the user first.
`scripts/gen_batch.py` drives the DashScope path and is suspended with it; for batches,
run `gen_image_codex.py` serially from a shell loop.

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
