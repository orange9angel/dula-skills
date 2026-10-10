# Three.js Procedural Character Modeling Techniques

Techniques distilled from public tutorials plus patterns reverse-engineered from the Dula asset library (`Doraemon.js`, `Zorak.js`, `DiscoWorm.js` are the working in-repo examples). This is the "hand-drawing" toolbox: every technique shapes geometry in code the way a sculptor adds clay.

## 1. Primitives as Clay

A cartoon character is 10–40 primitives. The art is in **non-uniform scale** and **placement**, not in the geometry count.

| Part | Geometry | Shaping trick |
|------|----------|---------------|
| Head / body | `SphereGeometry(r, 32, 32)` | `scale.y = 1.1` for an egg body; `scale.z = 0.8` for a flat face |
| Muzzle / belly patch | `SphereGeometry` | `scale.z = 0.5`, pushed forward on +Z so it reads as a patch |
| Arms / legs | `CapsuleGeometry(r, len, 4, 16)` | capsule reads as a limb with no extra work |
| Feet | `SphereGeometry` | `scale.set(1, 0.6, 1.4)` → shoe shape |
| Hands | `SphereGeometry` | plain ball for cute style |
| Collar / ring props | `TorusGeometry(R, tube, 16, 32)` | `rotation.x = Math.PI/2` to lie flat |
| Smile / brow curves | `TubeGeometry(QuadraticBezierCurve3, 20, 0.012, 8)` | any 2D curve becomes a 3D tube |
| Cones | `ConeGeometry` | ears, horns, beaks, hats |
| Organic bodies | `LatheGeometry(points, 32)` | revolve a 2D profile for vases, blobs, pear bodies |

Rules of thumb:

- Sphere segments: 32 for hero parts, 16 or less for tiny parts (performance).
- `castShadow = true` on the big masses (head, body) is enough; skip it on tiny parts.
- Overlap primitives generously — intersections are hidden by the toon shading and read as one shape.

## 2. Toon (Cel) Shading

Dula's house style, from `Doraemon.js`: `MeshToonMaterial` + a 4-step gradient map built on a canvas, `NearestFilter` on both filters so the shading bands are hard:

```js
const canvas = document.createElement('canvas');
canvas.width = 4; canvas.height = 1;
const ctx = canvas.getContext('2d');
const g = ctx.createLinearGradient(0, 0, 4, 0);
g.addColorStop(0, '#aaa'); g.addColorStop(0.4, '#ccc');
g.addColorStop(0.7, '#eee'); g.addColorStop(1, '#fff');
ctx.fillStyle = g; ctx.fillRect(0, 0, 4, 1);
const toonGradient = new THREE.CanvasTexture(canvas);
toonGradient.magFilter = THREE.NearestFilter;
toonGradient.minFilter = THREE.NearestFilter;

const mat = new THREE.MeshToonMaterial({ color: 0x0096e1, gradientMap: toonGradient });
```

Alternative from the wider community (same idea, no canvas): a `DataTexture` with `RedFormat` and 3–4 luminance steps. The canvas version above is preferred — it is what every existing Dula character uses.

Palette discipline: 3–5 flat colors total. One main color, one secondary, white, black, one accent. Cartoon readability comes from color blocking, not detail.

## 3. Inverted-Hull Outline (optional)

The classic anime outline: clone the mesh, scale it up ~1.03, flip it inside-out, render it black behind the original.

```js
const outline = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.BackSide }));
outline.scale.multiplyScalar(1.04);
group.add(outline); // add before/with the original mesh
```

Known caveats: outline width varies with local curvature; it doubles draw calls; it can look messy where many parts overlap. **Existing Dula characters do NOT use outlines** — only add them if the episode's art direction asks for it, and prefer doing it as a post-process (`PostProcessBase`) over per-mesh hulls.

## 4. Group Pivots (the joint system)

Primitives rotate around their own center — wrong for limbs. The fix is the core rigging idiom used by every Dula character:

1. Create a `Group` and position it at the **joint** (shoulder, hip, neck).
2. Add the mesh as a child, offset so the joint end is at the group origin (e.g. arm capsule at `position.y = -len/2`, hand at `-len`).
3. Rotate the **group**, never the mesh.

```js
const armGroup = new THREE.Group();
armGroup.position.set(sx, sy, sz);       // shoulder
const armMesh = new THREE.Mesh(new THREE.CapsuleGeometry(0.12, len, 4, 16), mat);
armMesh.position.y = -len / 2;           // top of capsule at shoulder
armGroup.add(armMesh);
```

Aim-at helper for limbs that connect two fixed points (from `Doraemon.js`): put the group at the shoulder, `group.lookAt(handX, handY, handZ)`, then `group.rotateX(-Math.PI/2)` so the group's -Y axis points at the hand; lay the capsule down -Y.

Face parts follow the same rule: eyes/pupils/lids live in a per-eye `Group` so pupils slide without leaving the eye; the whole face lives in `headGroup` so head turns carry everything.

## 5. Face Construction

The animatable face, front of head is **+Z**:

- **Eye**: white sphere (`scale.z = 0.5` to flatten against the head) → pupil sphere at local +Z (`userData.baseX/baseY` recorded for the eye-tracking system) → catchlight: tiny white sphere offset up-right of the pupil. Catchlights are the cheapest way to make a character look alive — always add them.
- **Eyelid**: half-sphere (`SphereGeometry(r, 24, 24, 0, Math.PI*2, 0, Math.PI*0.5)`) in the head color, `visible = false` when open; the blink system toggles it.
- **Eyebrow**: small capsule laid sideways (`rotation.z = Math.PI/2 ± angle`); expressions raise/angle them.
- **Mouth** (lip-sync structure): a `Group` containing an upper-lip smile curve (bezier tube), a lower-lip flattened sphere, and a dark cavity sphere (`MeshBasicMaterial`, dark red/black, hidden when closed). The mouth cue system scales this group from its base values — record `mouthBaseScaleX/Y/Z` and `mouthBaseY` right after positioning.

### Layered Anime Eye （大眼睛不"无神"的关键）

A single flat iris sphere always reads dead. The anime eye is a **stack of 5–6 flattened lenses** along +Z (verified in `Yuki.js` / `Kenta.js` / `Mochi.js`):

```
white (flattened, scale.z≈0.35)
 └ rim    — darker sphere slightly LARGER than the iris → the dark ring at iris edge
 └ iris   — main color, offset a hair downward
 └ glow   — small light-colored sphere at the iris BOTTOM → the "light pool"
 └ pupil  — dark, tall
 └ catchlights — one big top, one small bottom (never skip)
```

Rules: every lens except the white gets `userData.noSketch = true` (an ink hull around each layer tangles into scribble — learned the hard way). Only the eye white carries the sketch outline, plus a lash arc (thin torus arc) over the top for the classic anime upper lash line. For animal eyes, skip the white layer (e.g. Mochi: amber rim + slit pupil + one tiny catchlight keeps a deadpan face alive).

## 6. Proportion Recipes

- **Chibi / mascot (2 heads tall):** head diameter ≈ 50% of total height, body a squashed sphere, limbs stubby capsules, feet directly under the body. See `Doraemon.js`: head sphere r=0.7 at y=1.6, body r=0.65 at y=0.7.
- **Standard cartoon (4 heads):** head r ≈ 0.35–0.45 at y ≈ 1.5, torso a capsule or lathed profile, legs half the height.
- Keep total height in the 1.2–1.8 range and the ground contact at y=0, or the shared scenes/cameras will misframe the character.

## 7. Symmetry Idiom

```js
for (const side of [-1, 1]) {
  // side === -1 → character's left
  part.position.x = side * 0.18;
  if (side === -1) this.leftPart = part; else this.rightPart = part;
}
```

Mirror rotations by multiplying by `side`. Never write the same code twice with flipped signs.

## 8. Idle Life (update loop)

Override `update(time, delta)` — always call `super.update(time, delta)` first — for cheap ambient motion: antenna wobble (`rotation.z = Math.sin(time * 3) * 0.1`), prop spin, breathing (`body.scale.y = base + Math.sin(time * 2) * 0.01`). Keep it subtle; the animation system drives the big motion.

## 9. 赛璐璐材质统一（动漫化形象）

材质混搭是"不像动画片"的第一来源：皮肤/头发 Basic 平涂、衣服 Lambert、装甲 Phong 写实高光、场景 Toon 无 gradientMap 同框时，各部件对光的反应不在一个体系里（bio_armor_academy_s1e2 R21 前的状态）。

### toon ramp 配方

- gradientMap 用 canvas 做 3–4 阶（§2 的做法），每阶一个**纯色块**，不用渐变——渐变就是软明暗，违背赛璐璐阶梯。`NearestFilter` 双滤镜缺一不可。
- 各阶明度：3 阶取 0.45 / 0.72 / 1.0，4 阶取 0.38 / 0.6 / 0.82 / 1.0。
- 阴影阶不要纯灰：色相向蓝紫偏 10–20°、饱和度提高约 10%；受光阶向暖偏约 5°。赛璐璐的"上色感"来自色相随明暗阶梯走，纯灰阶梯读成石膏。

```js
// 4 阶冷阴影 ramp：阴影阶偏蓝紫，受光阶偏暖
const c = document.createElement('canvas'); c.width = 4; c.height = 1;
const x = c.getContext('2d');
['#6b6b8a', '#a39eb0', '#e8e2da', '#fffaf2'].forEach((v, i) => {
  x.fillStyle = v; x.fillRect(i, 0, 1, 1);
});
const ramp = new THREE.CanvasTexture(c);
ramp.magFilter = ramp.minFilter = THREE.NearestFilter;
// 全角色共享同一个 ramp：new THREE.MeshToonMaterial({ color, gradientMap: ramp })
```

- 逆光/黄昏场景正面全黑时，脸与小件用 `MeshBasicMaterial` 兜底（见 SKILL.md 踩坑记录：脸贴逆光全黑改 Basic）。Basic 件颜色要手工预调暗（×0.85–0.92），否则平涂比 toon 件亮一档。

### 材质混搭纪律

- 同一角色尽量单一光照模型：全身 `MeshToonMaterial` 共享同一个 gradientMap，皮肤/头发/衣服/装备一视同仁。
- 写实高光件（如殖装甲的 Phong）若要保留：①与角色主色同色系；②面积控制在全身 10% 以内；③高光强度压低。更稳的替代是 toon + 假高光贴图：在 canvas 纹理上直接画一道硬边白色高光带，零光照依赖，风格天然统一。

### 全身描边（法线外扩壳推广到躯干/四肢/装备）

- 头发壳描边工艺（`onBeforeCompile` 在 `begin_vertex` 后 `transformed += normal * width`、`BackSide`、`customProgramCacheKey` 按宽度分档）原样推广到躯干、四肢、装备；壳网格 add 为原网格子节点，跟随动画与 `visible` 开关。
- 线宽按部件半径分级（口诀：轮廓主干 > 四肢 > 细节）：躯干/头 0.0014，四肢 0.0010，手指/发束等细节件 0.0006。墨色统一暖近黑（如 `#3a3039`），不用纯黑。
- 已知风险：壳沿法线外扩会描到凹面内部（鼻/颊交界被描出假褶），凹面内漏的取舍规则见 [handdrawn-style.md](handdrawn-style.md) 的描边纪律；本集对策是皮肤不上壳、只给头发/装备上壳。

### 阴影

- cel 感要硬边阴影：硬切阴影与平涂色块、阶梯明暗是同一语言；`PCFSoftShadowMap` 的软边与色块打架。
- 日落逆光场景可保留软阴影但压淡（降低阴影不透明度到 0.4–0.6），软阴影只留给地面投影，角色自阴影交给 gradientMap 的阶梯表达。
