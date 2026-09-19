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

## Hands — Never Ball Hands

球端手臂是廉价 CG 的最大破绽（2026-09 监制明确点名的硬伤）。默认造型：

- **连指手套手（默认）**：压扁的胶囊体（手掌，scale z 约 0.45）+ 一个楔形/小胶囊拇指，
  与手臂用关节球衔接。 silhouettes 读出"手"而不是"球"。
- **四指卡通手（特写/手势重点镜头）**：手掌 + 4 根锥形短指（无小指分开的 realism，
  商业卡通惯例）。只在会出现在特写里的主角手上用。
- 手部形状挂在前臂组末端，继承 `leftArm/rightArm` 契约，不要替换枢轴组本身。

### 手型集（hand pose set）纪律

商业 2D 动画的手是作画监督画的**固定手型**，不是连续运动的关节手指——
我们也照此办理（2026-09 监制反馈"手指细节"后的定案）：

1. 为主角预雕 4-6 个固定手型：`fist`（握拳）/ `open`（张开）/ `point`（指）/
   `hold`（持物）/ `wave`（挥手张开），全部不可见切换（visible 切换或
   位置互换），不做手指关节动画。
2. 手型随动作语义切换：wave 动作用 open、拿道具用 hold、强调台词用 point。
   切换时机在姿态切换的同一帧（一拍二网格上），不要在中间帧渐变。
3. 关节手指不要做：Q 版比例读不出、建模绑定成本高、还会引入新的穿模面。
4. 脸部细节（睫毛/腮红/嘴内/高光）走 2D 贴片方向（脸基本朝相机），
   不要为此加 3D 几何。

若剧集追求商业动画观感，配合 `cel-look` skill 的完整纪律（描边/一拍二/赛璐璐阴影）。
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
- Skirt as open-ended cone (`CylinderGeometry(..., openEnded=true)`) → see-through interior / visible under skirt when lying or running: set `material.side = THREE.DoubleSide` and add a bloomers ellipsoid underneath as a permanent backstop; lengthen the skirt so it always covers the bloomers' lower edge (yuki_morning_battle 翻车史）.
- Leg/sock/shoe as separate meshes with mismatched axes → they rotate apart mid-swing and read as a broken leg: make them coaxial (replace a flattened-sphere shoe with a boot capsule on the leg axis), and do the swap *before* `sketchify()` so the new part also gets ink lines.
- Nested part's sketch hull pokes through the enclosing mesh (sock hull jags out of the shoe = "fracture line") → strip the inner part's strokes (remove its `userData.stroke`/`userData.sketchLine` children) or let the outer part fully cover the junction.
- Mirrored pair angles written as `value * side` → one side fans/flips wrong (Mochi's left whiskers fanned upward): sanity-check the `-1` side by hand; sign errors survive every screenshot until someone looks at a close-up.
- Spikes/tufts sized to sit exactly flush with a hair/shell surface get swallowed by it (Dodo's hair spikes: tip == cap top → invisible): size signature protrusions so tips clear the enclosing shell by a visible margin, then confirm from a front close-up.
