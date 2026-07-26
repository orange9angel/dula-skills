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
5. **Plan motion before generating.** Express an action as readable phases such as setup, anticipation, action, apex/contact, and recovery. Generate neighboring phases together. For long actions, use overlapping groups whose first frame is the prior approved anchor.
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
- **DashScope/Bailian:** read [dashscope-bailian.md](references/dashscope-bailian.md) and use `scripts/run_dashscope_sequence.py`.

Never claim a capability because another model from the same vendor supports it.

### 5. Review as a sequence

Inspect both individual frames and a chronological contact sheet. Check:

- face shape, eye color, hair silhouette, accessories, body proportions;
- wardrobe geometry, colors, numbers/logos, and left/right placement;
- character count, limb count, prop count, and hand-object contact;
- background layout, light direction, camera height, focal scale, and horizon;
- screen direction, foot placement, body balance, action progression, and prop trajectory;
- whether adjacent frames show actual motion rather than unrelated poses.

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
