---
name: character-modeler
description: Procedurally "hand-draw" new Dula cartoon characters in Three.js — sculpt with primitives, toon shading, jointed group pivots, and an animatable face — then register the character in dula-assets and verify it with rendered screenshots. Use when an agent needs to create a brand-new character for the Dula engine without external modeling tools or imported meshes.
---

# Character Modeler

Create a new Dula character entirely in code. "Hand-drawing" here means procedural modeling: composing Three.js primitives into a readable cartoon silhouette, with the face and joint structure the Dula animation system expects — then, optionally, giving it a true hand-drawn ink treatment (sketch mode) via `dula-engine/handdrawn`. No Blender, no GLTF imports, no textures from disk.

Keep the skill in `dula-skills/character-modeler/`. New characters live in `dula-assets/characters/<Name>.js` and are registered in `dula-assets/index.js`.

## Drawing Methods

The engine supports two looks. Decide with the user before building:

1. **Clean toon mode** (default) — smooth shapes, `MeshToonMaterial`, no line work. Matches all existing characters.
2. **Hand-drawn sketch mode** — the same geometry, plus wobbly ink outlines, overshoot detail strokes, and 12 fps "boiling" via `sketchify()` + `BoilSystem`. Read [references/handdrawn-style.md](references/handdrawn-style.md) before using it. Sketch mode is opt-in per character (subclass + register, or apply in an episode bootstrap) — never retrofit it onto existing characters without being asked.

## Boundaries

- Only use Three.js primitives (Sphere/Capsule/Cylinder/Box/Cone/Torus/Tube/Lathe) composed in code. Do not import external meshes, textures, or fonts.
- Match the look of existing characters: `MeshToonMaterial` + 4-step canvas gradient. Do not introduce new shading styles (PBR, custom shaders) unless the user asks.
- Follow the `CharacterBase` contract exactly — the animation, lip-sync, expression, and combat systems read specific fields. Read `dula-engine/characters/CharacterBase.js` and a reference character (`dula-assets/characters/Doraemon.js` is the canonical cute-style example) before writing code.
- Never claim the character looks right until you have rendered screenshots via `dula-verify` and inspected them.

## Load Context

- Read [references/modeling-techniques.md](references/modeling-techniques.md) for the collected Three.js hand-modeling techniques (primitive sculpting, toon shading, outline, pivots, face construction, proportions).
- Read [references/handdrawn-style.md](references/handdrawn-style.md) for sketch mode (ink strokes, sketchify, boiling) when the user wants a hand-drawn look.
- Read [references/characterbase-contract.md](references/characterbase-contract.md) for the exact fields the engine expects.
- Read `dula-assets/characters/Doraemon.js` (round cute) and one humanoid (e.g. `Zorak.js`) as working code references.

## Workflow

1. **Design on paper first.** Pick a silhouette (circle = cute/friendly, square = sturdy, triangle = dynamic), a proportion recipe (chibi ≈ 2 heads tall; standard ≈ 4–5 heads), a 3–5 color palette, and 2–3 signature features (antenna, bell, scar...). Target total height ≈ 1.2–1.8 world units so the character fits existing scenes and cameras.
2. **Build bottom-up:** root `this.mesh` → body → `headGroup` → face (eyes/pupils/catchlights/eyelids/eyebrows/mouth) → arms/legs as pivot groups → signature props.
3. **Use the symmetry idiom:** build paired parts in a `for (const side of [-1, 1])` loop; left is `side === -1`.
4. **Wire every contract field** listed in the contract reference: `headGroup`, `mouth` (+ `mouthBase*` backup values), `leftPupil/rightPupil` (+ `userData.baseX/baseY`), `leftEyelid/rightEyelid`, `leftEyebrow/rightEyebrow`, `leftArm/rightArm` (+ `*BaseZ`), `leftLeg/rightLeg`, `archetypes`, `boundingRadius`.
5. **Register** in `dula-assets/index.js`: import the class, add `registerCharacter('<Name>', <Name>)` inside `registerAll()`, and export it if the file exports other characters.
6. **(Sketch mode only)** Apply `sketchify()` + `BoilSystem` per handdrawn-style.md, and set `userData.noSketch = true` on pupils/eyelids/catchlights/hidden parts in `build()`.
7. **Verify visually** (see below). Iterate on proportions/positions from screenshots, not from imagination. In sketch mode, check at one close-up and one full-body distance: outlines must not swallow small features, and dark parts must not carry invisible ink.

## Visual Verification

Create a minimal showcase episode under `dula-story/episodes/<name>_showcase/`:

- `bootstrap.js`: `import { registerAll } from 'dula-assets'; registerAll();`
- `script.story`: one `@<Scene>` entry, one `{Position:<Name>|...}` placement, then 2–4 second beats with `{Camera:Static|position=...|lookAt=...}` at different distances (full body, half body, face close-up) plus a few expression tags (`{FaceHappy}`, `{FaceDetermined}`, dialogue for mouth movement).

Then from `dula-story/`:

```shell
npx dula-verify ./episodes/<name>_showcase
```

Open the screenshots in `episodes/<name>_showcase/storyboard/` (or the path the verifier prints) and actually look at them. Check: silhouette readability, face symmetry, no interpenetrating geometry, feet on the ground plane, mouth/eyes on the front of the head (+Z), scale vs. scene. Fix and re-render until clean. Delete the showcase episode only if the user wants it removed.

## Common Failures

- Face buried inside the head sphere → move face parts forward on +Z until they sit on the surface; sphere radius r ⇒ surface at z = r.
- Arms rotate from the elbow/wrong pivot → the arm *group* must be at the shoulder with the capsule mesh offset downward inside it.
- Character floats or sinks → check the lowest foot point vs. `y=0` ground; adjust leg group positions, not the root.
- Flat look → gradient map must use `NearestFilter`; check the scene actually has directional light.
- Blink/viseme/lip-sync not working → a contract field is missing or misnamed; compare against `Doraemon.js` line by line.
- Character never appears in the render at all → characters only spawn when an entry *mentions* them (`[Speaker]` line or `{Event:...|character=X}`); a Position tag alone does not spawn. Silent characters need an `Event:Move` mention.
- Character buried inside a scene prop (fountain, furniture) → before choosing coordinates, render one wide shot of the empty scene and note where its big props stand; ParkScene's center pond/fountain is the classic trap.
