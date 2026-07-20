# Hand-Drawn Style (Sketch Mode)

The engine's default look is *clean CG toon* — perfect smooth shapes, no line work. This reference describes the second drawing method: **hand-drawn sketch mode**, which imitates how an animator actually draws. It is implemented by `dula-engine/handdrawn/` and can be layered on any procedural character without changing its geometry.

## What Makes Something Look Hand-Drawn

Distilled from Blender Grease Pencil / Freestyle workflows and 2D animation practice:

1. **Strokes are objects.** In Grease Pencil every line is a vector stroke with pressure (width) — not a shader trick. Our equivalent: `createStroke()` builds a variable-width tube along points.
2. **No perfect lines.** Real strokes have pressure variation, end taper, and slight positional wobble. Perfectly straight/circular lines are the #1 CG giveaway.
3. **Boiling.** Hand animation is redrawn every 1–2 frames, so lines shimmer. CG lines are frozen. `BoilSystem` re-jitters line vertices at 12 fps ("on twos") — deterministic per tick, so offline renders stay reproducible.
4. **Redrawn contours are doubled and wrong.** Sketch artists overshoot and double strokes. `sketchify()` adds per-vertex width jitter to outlines and midpoint overshoot to detail strokes.
5. **Ink does not shade.** Stroke materials are unlit (`MeshBasicMaterial`); only fills receive light.

## The Drawing Method

```
角色几何（捏粘土，见 modeling-techniques.md）
        │
        ▼
sketchify(character.mesh, {...})     ← 给每个部件描边
        │
        ▼
BoilSystem.add(mesh); 在 update() 里 BoilSystem.update(time)
        │
        ▼
渲染 = 动画拍摄一帧帧"重画"的手稿
```

Two outline techniques run together:

- **Silhouette hull** — inverted hull (BackSide copy pushed along normals), but each vertex's offset is jittered per-seed, so the contour wobbles like a redrawn line. This is the ONLY technique that works on smooth spheres/capsules — `EdgesGeometry` finds nothing on smooth geometry.
- **Detail strokes** — hard edges over `threshold` degrees are redrawn as real strokes with midpoint overshoot. Catches panel borders, cylinder rims, box corners.

## API Quick Reference

```js
import { sketchify, BoilSystem, createStroke, strokeCircle, strokeArc, strokeLine, createHatchTexture } from 'dula-engine';

class SketchGulu extends Gulu {
  build() {
    super.build();
    sketchify(this.mesh, {
      color: 0x25222a,   // ink — warm near-black, never pure #000
      width: 0.013,      // hull offset in LOCAL units of each mesh (auto-shrinks for small parts)
      threshold: 40,     // degrees; lower = more detail strokes
      seed: 7,           // keep fixed per character for stable identity
    });
    BoilSystem.add(this.mesh, { amplitude: 0.0045, fps: 12 });
  }
  update(time, delta) {
    super.update(time, delta);
    BoilSystem.update(time);   // idempotent per tick — every character may call it
  }
}
```

`sketchify` returns `{ strokes }`; outlines are parented under each source mesh, so they follow animation, scale, and `visible` toggles for free.

## Parameter Recipes

| Goal | Settings |
|------|----------|
| Clean anime line | `width: 0.010`, boil `amplitude: 0.002, fps: 12` |
| Pencil sketch | `width: 0.014`, boil `amplitude: 0.005, fps: 8` |
| Marker / thick ink | `width: 0.020`, boil `amplitude: 0.003` |
| Still illustration (no boil) | omit `BoilSystem` entirely |

Freehand details (scars, seams, text, decorations) — draw them as strokes parented to the part:

```js
const seam = strokeArc(0.3, 0.3, Math.PI * 0.2, Math.PI * 0.8, { width: 0.006, color: 0x25222a, seed: 11 });
seam.position.set(0, 0.2, 0.40);   // on the belly panel
this.mesh.add(seam);
BoilSystem.addMesh(seam, { amplitude: 0.002 });
```

`createHatchTexture({ layers: 1|2|3, spacing, angle })` makes a canvas pencil-hatch texture; use it as `material.map` on flat fill areas (panels, clothing) when you want shaded hatching instead of flat color.

## Rules and Pitfalls

- **Protect small face parts.** Pupils, eyelids, catchlights, hidden mouth cavities must NOT get outlines — set `userData.noSketch = true` on them in the character's `build()`. Ink around a 3 cm pupil swallows the whole eye.
- **A line never gets an outline.** Lash arcs, lip tubes, brow capsules, thin rings (hair ties, antenna stems) are already strokes — hulling them doubles them into blobs. Mark them `noSketch` too. (Learned from SketchYuki's eye-scribble incident.)
- **Nested lenses tangle.** Two parts whose outlines nearly touch (eye white + iris 0.018 apart) merge into scribble. Keep ink on the outermost layer only.
- **Outline width adapts automatically** (`min(width, radius * 0.3)`), but tiny thin features are still better excluded.
- **Dark-on-dark is pointless**: a dark ink hull around a black pupil on a dark screen adds vertices and mud. Exclude.
- **Boil only the lines**, never the base mesh — boiling fills wobbles shading and looks broken.
- **Keep seeds fixed.** A character's wobble pattern is part of its identity; random seeds per run make every render different (and break re-render reproducibility).
- Hull is BackSide — it does not work on open/flat geometry (planes); use strokes there.
- Extra cost: roughly doubles draw calls per outlined part. Sketch mode is for hero characters, not crowds.

## Scenes: Sketch the Background, Never Boil It

Real hand-drawn animation paints backgrounds **once** — only characters boil. Apply the same split:

```js
// bootstrap.js — subclass the scene, sketchify after build, no BoilSystem
class SketchRoom extends RoomScene {
  build() {
    const scene = super.build();
    sketchify(scene, {
      color: 0x2a2a32, width: 0.02, threshold: 45,
      filter: (mesh) => {
        const t = mesh.geometry?.type;
        if (t === 'PlaneGeometry' || t === 'CircleGeometry') return false; // ground/water: hull needs closed volume
        mesh.geometry.computeBoundingSphere?.();
        return mesh.geometry.boundingSphere.radius <= 4;                  // skip sky/backdrop-scale meshes
      },
    });
    return scene;
  }
}
registerScene('RoomScene', SketchRoom);
```

Props (furniture, trees, benches) read beautifully with static ink; ground, water discs and sky must be filtered out — the inverted hull is BackSide and has nothing to shell on a plane.

## Eye Contact: SceneDirector Gaze

Hand-drawn acting dies when characters stare past each other. The engine's fix is not eye geometry but body language:

- `{SceneDirector:Gaze|mode=auto}` — everyone faces whoever is speaking; the speaker faces the audience center. Put it in the scene-establishing entry for dialogue-driven episodes.
- `{SceneDirector:Gaze|mode=fixed|target=Mochi}` — the whole cast stares at one target (great for "everyone looks at the cat/prop" beats).
- `{SceneDirector:Gaze|mode=free}` — releases control (chases, montages).
- Manual `face=` in a Position tag **overrides** auto gaze — use it to repair a closeup where auto-facing puts the speaker's back to camera (e.g. `face=Yuki` when Kenta consults her).
