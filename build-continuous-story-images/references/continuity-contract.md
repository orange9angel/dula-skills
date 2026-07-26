# Continuity contract

Use one JSON sequence plan as the source of truth for narrative intent, visual locks, provider capabilities, outputs, and review state.

## Plan structure

`init_sequence.py` creates the supported schema. Keep these sections:

- `schemaVersion`: contract version. Current value is `1`.
- `sequenceId`: stable lowercase identifier for the action group.
- `source`: optional story, storyboard, or timing source.
- `paths.projectRoot`: project root relative to the plan file.
- `paths.outputDirectory`: generated-frame directory relative to the project root.
- `provider`: selected provider, model, declared capabilities, and non-secret options.
- `continuity`: master references, hard locks, negative constraints, and grouping policy.
- `shots`: ordered action phases and their review/output state.
- `runs`: append-only generation records. Do not store API keys or bearer tokens.

## Reference roles

Keep reference roles distinct:

- `identityReferences`: canonical face, hair, body proportions, and signature accessories.
- `styleReferences`: line work, rendering, palette, and texture.
- `settingReferences`: spatial layout, lighting direction, and persistent background objects.
- `referenceFrame`: a reviewed sequence frame used to preserve immediate temporal state.

An image may serve more than one role, but record each intended role. More references are not automatically better: remove references that contradict the current wardrobe, angle, age, or visual style.

## Hard locks

Write facts that can be verified visually:

```json
{
  "characters": [
    "one teenage girl",
    "amber-brown eyes",
    "deep teal high ponytail ending near the shoulder blades",
    "two gold hair clips on her left temple"
  ],
  "wardrobe": [
    "white sleeveless jersey with navy side stripes and navy number 07",
    "one red wristband on her right wrist"
  ],
  "scene": [
    "empty modern indoor basketball gym",
    "single visible basket at frame left"
  ],
  "camera": [
    "16:9 landscape",
    "eye-level three-quarter front view",
    "full body with constant subject scale"
  ],
  "style": [
    "original Japanese 2D animation",
    "clean cel shading and crisp line art"
  ],
  "props": [
    "exactly one orange basketball"
  ]
}
```

Avoid subjective locks such as “looks good” or “same vibe.” Avoid conflicting facts across categories.

## Shot state

Each shot contains:

- `id` and `order`;
- `actionPhase`;
- `description`;
- `stateBefore` and `stateAfter`;
- `allowedChanges`;
- `preserve`;
- `referenceFrame`;
- `status`;
- `output`;
- `review`.

Use `stateBefore` and `stateAfter` for facts that must connect across frames:

```json
{
  "stateBefore": {
    "body": "knees bent, both feet planted",
    "ball": "held at waist"
  },
  "stateAfter": {
    "body": "rising, toes leaving floor",
    "ball": "moving from waist toward chest"
  }
}
```

The next shot should begin from compatible state. The validator reports contradictory shared keys.

## Allowed changes and preservation

Keep the default preservation set:

- `character identity`
- `wardrobe`
- `body proportions`
- `scene geometry`
- `lighting`
- `camera`
- `visual style`
- `screen direction`

Typical allowed changes are:

- `pose`
- `expression`
- `gaze`
- `moving prop position`
- `secondary motion`

Do not put identity, wardrobe, scene, or camera in `allowedChanges` unless the story requires a visible transition. Start a new sequence group for a hard cut.

## Group boundaries

Keep one group when:

- the action is continuous;
- the camera setup is stable;
- the same characters, wardrobe, scene, and style persist;
- the provider can return an ordered sequential group.

Split the group when:

- there is a deliberate cut or large lens/angle change;
- the location or time of day changes;
- a transformation changes identity or wardrobe;
- the provider's reliable group size is exceeded.

For a long action, overlap adjacent groups by one approved anchor:

```text
group A: shot 01 02 03 04 05
group B:             05 06 07 08 09
```

Do not publish the overlap twice.

## Review states

Use:

- `planned`: not generated;
- `generated`: output exists but is not reviewed;
- `accepted`: visually approved and safe to inherit;
- `needs_repair`: mostly correct and suitable for a local edit;
- `rejected`: must not be inherited.

In final mode, every shot must be `accepted`, have an existing output, and avoid a rejected `referenceFrame`.

## Run records

Append one object per provider attempt:

```json
{
  "runId": "20260726T120000Z-group",
  "provider": "dashscope",
  "model": "wan2.7-image-pro",
  "mode": "sequential-group",
  "shotIds": ["shot_01", "shot_02"],
  "referencePaths": ["assets/character_reference.png"],
  "taskId": "provider-task-id",
  "seed": null,
  "outputs": ["assets/images/jump/shot_01.png"],
  "createdAt": "2026-07-26T12:00:00Z"
}
```

Record reproducibility data but never credentials, authorization headers, base64 image bodies, or signed download URLs.
