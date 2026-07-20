# Scene Contract v1

Use `dula-story/episodes/<episode>/config/scene_contract.json`. The JSON Schema is [scene-contract.schema.json](scene-contract.schema.json).

The contract records high-risk visual semantics that can be validated. It is not a dump of every Three.js mesh, material, line of dialogue, or audio cue.

## Top-Level Shape

```json
{
  "$schema": "../../../../../dula-skills/scene-designer/references/scene-contract.schema.json",
  "contractVersion": "1.0",
  "episode": "episode_name",
  "sourceStory": "script.story",
  "intent": {
    "premise": "One physical sentence describing the scene problem.",
    "audience": "Target audience",
    "designPriorities": ["readable silhouettes", "prop-driven causality"]
  },
  "registrations": {
    "bootstrap": "bootstrap.js",
    "scenes": ["RegisteredScene"],
    "characters": ["Hero"]
  },
  "scenes": [],
  "entities": [],
  "state": {},
  "events": [],
  "blocking": [],
  "shotChecks": [],
  "acceptance": {
    "staticChecks": ["scene-tool", "story-tool", "node-check"],
    "runtimeChecks": ["dula-inspect-team", "dula-verify", "visual-review"]
  }
}
```

## Scenes

Each `scenes[]` item defines:

- `registryName`: exact runtime registration used by `@Scene`.
- `implementation`: `official`, `alias`, `extend`, or `episode-local`, plus module/export/bootstrap/readiness.
- `intent`: location, time, tone, story function, and concrete readability rules.
- `coordinates`: world unit/up axis/ground plane. Do not use this as a character-facing convention.
- `stage.bounds`: supported world volume.
- `stage.zones`: walkable, performance, landing, or camera-safe regions.
- `stage.anchors`: named world/local positions for reasoning and implementation. Runtime does not consume anchors automatically.
- `lighting`: semantic mood and rules that preserve faces and prop silhouettes.
- `cameraObstacles`: only `sphere`, `capsule`, or `box`.
- `audioAnchors`: semantic sound sources or ambience regions; no audio filenames are generated here.
- `dependencies`: external assets plus readiness behavior. Async scene loading must expose `readyPromise`.

## Entities And Space

Every important character or prop needs a stable `id`, scene, binding, parent, initial transform, and presence. Props also define states.

```json
{
  "id": "fork2",
  "scene": "KitchenScene",
  "kind": "prop",
  "objectName": "Fork2",
  "binding": "utensils[1]",
  "parent": "utensilRack",
  "initialPresence": "onstage",
  "initial": {
    "visible": true,
    "transform": {
      "space": "local",
      "relativeTo": "utensilRack",
      "position": [-0.16, 0.64, 0.05]
    }
  },
  "states": ["hanging", "detached", "at-timer"],
  "initialState": "hanging"
}
```

Rules:

- `world` transforms use `relativeTo: "$scene"`.
- `local` transforms use the current `parent` as `relativeTo`.
- Use `scene.attach(child)` when reparenting while preserving world transform.
- A world-space motion under a non-scene parent requires an earlier `reparent` effect or an explicit `conversion`.
- Character `visualForwardAxis` is per model. Confirm it with a facing check; do not infer it from the world forward axis.

## Events And State

Contract every non-engine `{Event:X}`. `tag` is story spelling; `handler` is the scene method. Normal dispatch accepts `lowerFirst(tag)` or the exact tag and passes no arguments.

Effects in v1:

- `setState`: update a declared scene state binding.
- `setEntityState`: move a prop through its declared visual states.
- `presence`: move a character between `offstage`, `onstage`, and `concealed`.
- `reparent`: change an entity parent and state whether world transform is preserved.
- `motion`: describe entity motion and coordinate space.

```json
{
  "tag": "TimerEscape",
  "scene": "KitchenScene",
  "handler": "timerEscape",
  "argumentMode": "none",
  "durationSeconds": 3.7,
  "requires": ["BowlTrap"],
  "effects": [
    { "op": "reparent", "entity": "fork2", "to": "$scene", "preserveWorld": true },
    {
      "op": "motion",
      "entity": "fork2",
      "space": "world",
      "relativeTo": "$scene",
      "from": "current",
      "to": { "entity": "timer", "offset": [0, 0.04, 0.13] },
      "tolerance": 0.1
    }
  ]
}
```

`requires` must match story order. Effects must match implementation side effects, including visibility and parenting.

## Blocking

Use `blocking[]` for first-frame positions and intentional movement. Each item identifies the character, scene, story entry, world start/end, zone, clearance, and dramatic purpose. The contract does not silently edit the story: required placement must also exist in `Position`/`Move` tags or scene code.

## Critical Shots

`shotChecks[]` covers meaning-bearing shots rather than duplicating every camera cue. Reference the actual story `entry` and an `offsetSeconds` inside that entry.

Record:

- `mustSee`: entity, optional focus point, safe margin, minimum frame area, maximum occlusion, and facing threshold.
- `mustHavePresence`: character visibility semantics at that moment.
- `mustShowTogether`: entities whose relationship must be legible in one frame.

Always add a check for a reveal, concealment, prop handoff, irreversible state change, visual punch line, and any camera type without collision guarding.

## Acceptance

Static validation proves schema, registrations, event coverage, references, state order, coordinate-space consistency, bounds, and shot declarations. It cannot prove projected size or real occlusion. Finish with `dula-verify`, exact-time screenshots for critical shots, and visual inspection.
