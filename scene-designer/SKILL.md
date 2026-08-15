---
name: scene-designer
description: Design, implement, or revise executable Dula scenes from story semantics. Use when an agent must translate a `script.story` episode into spatial staging, scene selection, character blocking, interactive prop state machines, custom scene events, lighting, camera obstacles, critical shot requirements, and semantic ambience anchors; create or update `config/scene_contract.json`, episode-local `scenes/*.js`, and scene registrations; or diagnose scene continuity, coordinate-space, visibility, event-handler, and camera-readability problems before audio and rendering.
---

# Scene Designer

Translate dramatic intent into a validated visual contract and Dula runtime implementation. Keep this skill in `dula-skills/scene-designer/`; write episode artifacts only under `dula-story/episodes/<episode>/`.

## Boundaries

- Own `config/scene_contract.json`, scene selection, `scenes/*.js`, scene registration, spatial blocking, props, lighting, camera obstacles, and critical shot checks.
- Do not rewrite dialogue, timing, music, SFX, voice configuration, generated audio, or video. In integration work, adjust only scene, `Position`, `Camera`, or `Event` tags when the visual contract requires it.
- Describe ambience with semantic `audioAnchors`; leave audio files and mixing to the audio skills.
- Declare character and animation requirements, but implement those modules only when the user also requested them or the episode cannot run without them.
- Prefer registered official scenes. Use an alias only for a real registered subclass; create an episode-local scene when the story needs new geometry, stateful props, or event handlers.

## Load Context

- Read [references/scene-contract.md](references/scene-contract.md) before creating or changing a contract.
- Read [references/dula-scene-runtime.md](references/dula-scene-runtime.md) before editing scene JavaScript, bootstrap registrations, custom events, coordinate spaces, or camera obstacles.
- For 2D keyframe sequence scenes (`*SequenceScene.js` with source-space procedural layers), read [references/2d-sequence-scene-layers.md](references/2d-sequence-scene-layers.md) — layer coordinates must be measured, never eyeballed.
- Read the target `script.story`, `bootstrap.js`, existing scene/config files, and only the character modules needed for scale and focus points.

Extract facts before making design choices:

```powershell
python dula-skills/scene-designer/scripts/scene_tool.py inventory `
  --episode-dir dula-story/episodes/<episode> --json
```

Create a non-overwriting contract scaffold when none exists:

```powershell
python dula-skills/scene-designer/scripts/scene_tool.py scaffold `
  --episode-dir dula-story/episodes/<episode>
```

`inventory` is factual and read-only. `scaffold` creates structure but deliberately leaves semantic `TODO` values for the current agent to resolve; never treat the scaffold as a finished design.

## Workflow

1. **Read the story as staging.** Identify each location, scene function, time of day, tone, cast, entrances/exits, physical rules, visual punch lines, irreversible prop changes, and shots whose meaning depends on visibility or facing.
2. **Inventory the runtime.** Run `inventory`. Reuse reachable registrations and record missing scene, character, prop, event, or camera needs without inventing engine names.
3. **Choose a scene strategy.** Select `official`, `alias`, `extend`, or `episode-local`. Keep one contract for the episode with one entry per scene.
4. **Write the contract first.** Resolve every `TODO`. Define world bounds, walkable zones, anchors, first-frame blocking, entity parents and coordinate spaces, prop states, event pre/postconditions, visibility semantics, critical shots, lighting, obstacles, dependencies/readiness, and ambience anchors.
5. **Implement against the contract.** Register scenes through the reachable bootstrap. Make each scene zero-argument constructible. Build static geometry before characters exist. Put mutable story state on the scene instance and make event/update behavior deterministic under replay.
6. **Validate statically.** Fix every error from `scene_tool validate`. Warnings require an explicit design reason; do not silence them with fake contract entries.
7. **Run repository gates.** Check JavaScript syntax, strict story vocabulary, team inspection, Dula verification, and visual review. A successful render does not prove event coverage, coordinate correctness, or subject readability.
8. **Hand off.** Report contract and implementation paths, validation results, intentional warnings, critical shot evidence, and remaining character/audio/render work.

## Validation

```powershell
python dula-skills/scene-designer/scripts/scene_tool.py validate `
  --contract dula-story/episodes/<episode>/config/scene_contract.json `
  --episode-dir dula-story/episodes/<episode> `
  --warnings-as-errors
```

Use `inspect` for a concise human-readable design and risk summary:

```powershell
python dula-skills/scene-designer/scripts/scene_tool.py inspect `
  --contract dula-story/episodes/<episode>/config/scene_contract.json `
  --episode-dir dula-story/episodes/<episode>
```

Then run from the repository root and `dula-story` as appropriate:

```powershell
node --check dula-story/episodes/<episode>/scenes/<Scene>.js
python dula-skills/story-writer/scripts/story_tool.py validate `
  --story dula-story/episodes/<episode>/script.story `
  --episode-dir dula-story/episodes/<episode> --warnings-as-errors
cd dula-story
npx dula-inspect-team ./episodes/<episode>
npx dula-verify ./episodes/<episode>
```

Visually inspect every generated shot. For critical shots, verify the exact contract entry and offset rather than assuming storyboard filenames represent uniform time intervals.

## Non-Negotiable Runtime Rules

- Custom `{Event:RevealCake}` dispatches to `revealCake()` with no options. Do not rely on custom event parameters unless the engine explicitly handles that event.
- A prop animated in world coordinates must be parented to the scene, reparented with `scene.attach()`, or explicitly converted into parent-local coordinates.
- Hiding a character is a story state: record `offstage`, `onstage`, or `concealed`, the concealing prop, and the later reveal/exit.
- Anchors and zones are contract conventions, not current `SceneBase` APIs. Materialize required blocking in `Position`/`Move` tags or scene code.
- Only `sphere`, `capsule`, and `box` camera obstacles are supported. Cameras without collision guarding need critical shot checks.
- `build()` runs before characters are added. Async assets must expose a scene `readyPromise` consumed by the renderer.
