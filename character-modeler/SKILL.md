---
name: character-modeler
description: Procedurally "hand-draw" new Dula cartoon characters in Three.js — sculpt with primitives, toon shading, jointed group pivots, and an animatable face — then register the character in dula-assets and verify it with rendered screenshots. Use when an agent needs to create a brand-new character for the Dula engine without external modeling tools or imported meshes.
---

# Character Modeler

Create a new Dula character entirely in code. "Hand-drawing" here means procedural modeling: composing Three.js primitives into a readable cartoon silhouette, with the face and joint structure the Dula animation system expects — then, optionally, giving it a true hand-drawn ink treatment (sketch mode) via `dula-engine/handdrawn`. No Blender, no GLTF imports, no textures from disk.

Keep the skill in `dula-skills/character-modeler/`. New characters live in `dula-assets/characters/<Name>.js` and are registered in `dula-assets/index.js`.

This skill covers the primitive-based construction route. When final-shot quality requires continuous limb contours, articulated elbows/knees, camera-specific shape correction, or imported rigged meshes, use [direct-animation-craft](../direct-animation-craft/SKILL.md). The primitive-only choice below is not a project-wide restriction or a guarantee of production quality.

## Drawing Methods

This workflow has two existing looks. Follow the user's established choice; clarify only when an unresolved style choice materially changes the work:

1. **Clean toon mode** (default) — smooth shapes, `MeshToonMaterial`, no line work. Matches all existing characters.
2. **Hand-drawn sketch mode** — the same geometry, plus wobbly ink outlines, overshoot detail strokes, and 12 fps "boiling" via `sketchify()` + `BoilSystem`. Read [references/handdrawn-style.md](references/handdrawn-style.md) before using it. Sketch mode is opt-in per character (subclass + register, or apply in an episode bootstrap) — never retrofit it onto existing characters without being asked.

## Boundaries

- For the primitive-only task this skill describes, use Three.js primitives (Sphere/Capsule/Cylinder/Box/Cone/Torus/Tube/Lathe) composed in code. If that representation cannot meet the requested silhouette or deformation, explain the limitation and follow the production route above instead of treating this constraint as universal.
- Match the look of existing characters: `MeshToonMaterial` + 4-step canvas gradient. Do not introduce new shading styles (PBR, custom shaders) unless the user asks.
- Follow the `CharacterBase` contract exactly — the animation, lip-sync, expression, and combat systems read specific fields. Read `dula-engine/characters/CharacterBase.js` and a reference character (仓库内的 Q 版角色范例 `dula-assets/characters/Doraemon.js`) before writing code.
- Never claim the character looks right until you have rendered screenshots via `dula-verify` and inspected them.
- If the user explicitly requests no visual inspection, follow that constraint. Use bounded poses and numeric geometry checks, deliver a video for the user's review, and describe the character's appearance as unreviewed. Do not treat numeric clearance as artistic approval.

## Load Context

- Read [references/modeling-techniques.md](references/modeling-techniques.md) for the collected Three.js hand-modeling techniques (primitive sculpting, toon shading, outline, pivots, face construction, proportions).
- Read [references/handdrawn-style.md](references/handdrawn-style.md) for sketch mode (ink strokes, sketchify, boiling) when the user wants a hand-drawn look.
- Read [references/characterbase-contract.md](references/characterbase-contract.md) for the exact fields the engine expects.
- Read [references/anime-expression-symbols.md](references/anime-expression-symbols.md) 动漫表情符号化：汗滴/爆筋/豆豆眼/黑线脸等符号的语义表、绘制配方、触发纪律与夸张表情拓扑。
- Read `dula-assets/characters/Doraemon.js` (round cute) and one humanoid (e.g. `Zorak.js`) as working code references.
- 可执行积木：`dula-assets/lib/craft3d/`（surface/hand/pose/look/locomotion）是本 skill 造型工艺的共享代码形态；已验收的完整角色参考 `dula-assets/characters/bioarmor/`（《9章》系列）。新角色优先基于这些积木搭建，不要从 episode 目录拷贝。
- 有限站姿新角色参考 `characters/bioarmor/QianTangKuiCraft.js`；真实袖/手对躯干探针在
  `lib/craft3d/body-audit.js`，边界见 [有限动作试验](../direct-animation-craft/references/collision-prevention.md)。
  先量实际鞋底最低点、袖根以外表面与手部；不可直接沿用旧角色踝高或把骨轴在体外当成净空。

## Workflow

1. **Design on paper first.** Pick a silhouette (circle = cute/friendly, square = sturdy, triangle = dynamic), a proportion recipe (chibi ≈ 2 heads tall; standard ≈ 4–5 heads), a 3–5 color palette, and 2–3 signature features (antenna, bell, scar...). Target total height ≈ 1.2–1.8 world units so the character fits existing scenes and cameras.
2. **Build bottom-up:** root `this.mesh` → body → `headGroup` → face (eyes/pupils/catchlights/eyelids/eyebrows/mouth) → arms/legs as pivot groups → signature props.
3. **Use the symmetry idiom:** build paired parts in a `for (const side of [-1, 1])` loop; left is `side === -1`.
4. **Wire every contract field** listed in the contract reference: `headGroup`, `mouth` (+ `mouthBase*` backup values), `leftPupil/rightPupil` (+ `userData.baseX/baseY`), `leftEyelid/rightEyelid`, `leftEyebrow/rightEyebrow`, `leftArm/rightArm` (+ `*BaseZ`), `leftLeg/rightLeg`, `archetypes`, `boundingRadius`.
5. **Register** in `dula-assets/index.js`: import the class, add `registerCharacter('<Name>', <Name>)` inside `registerAll()`, and export it if the file exports other characters.
6. **(Sketch mode only)** Apply `sketchify()` + `BoilSystem` per handdrawn-style.md, and set `userData.noSketch = true` on pupils/eyelids/catchlights/hidden parts in `build()`.
7. **Verify visually** (see below). Iterate on proportions/positions from screenshots, not from imagination. In sketch mode, check at one close-up and one full-body distance: outlines must not swallow small features, and dark parts must not carry invisible ink.

## Hands — Never Ball Hands

球端手臂是廉价 CG 的最大破绽（2026-09 监制明确点名的硬伤）。默认造型：

- **连指手套手（默认）**：压扁的胶囊体（手掌，scale z 约 0.45）+ 一个楔形/小胶囊拇指，
  原型可用关节球衔接，但最终轮廓需平顺，避免露出球形鼓包和腕部黑圈；剪影应能读出掌面与拇指。
- **分指卡通手（特写/手势重点镜头）**：手掌 + 有长短层次的指组 + 拇指。四指设定为三根主指加拇指，五指设定为四根主指加拇指；沿用角色样板，不强制统一指头数量。近景重点检查掌面、腕口和拇指方向。
- 手部形状挂在前臂组末端，继承 `leftArm/rightArm` 契约，不要替换枢轴组本身。

### 手型集（hand pose set）纪律

固定手型是当前程序 Q 版角色的一种经济方案；真实制作也可使用连续手指变形或逐帧绘制。按镜头是否需要抓握、展开和转面选择：

1. 按实际镜头建立手型，例如 `fist`（握拳）/ `open`（张开）/ `point`（指）/
   `hold`（持物）/ `wave`（挥手张开）。切换模型时统一腕口、尺寸、掌面方向与持物锚点。
2. 手型跟随动作语义和曝光节奏；需要观众看到的抓握/张开过程应有中间形或关节动画，不能一律瞬切。
3. 远景可简化指组，近景可增加指关节或替换绘制。以实际播放尺寸的轮廓、接触和过渡验收，不以骨骼数量判断质量。
4. 脸部细节可用 2D 贴片控制图形；侧脸、转头与遮挡另行检查，避免始终朝相机而露馅。

若剧集需要提升最终镜头质量，先按 `direct-animation-craft` 检查造型和动作，再用 `cel-look` 整理线条、色块与曝光节奏。

## 服装-身体一体化建造纪律（S1E3 拍摄期翻车倒逼）

衣物与身体的冲突在 S1E3 全部拖到拍摄期才暴露（外套襟穿手、短袖终点+肘凸读成
"多一节"、静息手够不到大腿）。新角色在**建造期**就要按本节规避，技术做法见
[references/modeling-techniques.md](references/modeling-techniques.md) 第 10 节：

1. **袖子是肢体件的一部分**：袖筒与上臂挂同一 group、同 twoBone 数据同步更新，
   不许做成躯干上的静态套筒。短袖终点必须盖过肘最大屈曲时的肘尖活动域
   （屈曲 140° 时肘尖后移量），否则屈伸露断口；终点+肘凸+长裸前臂同框读成
   "多一节"（S1E3 P21 实录）。
2. **襟摆/裙摆建造期即挂铰链 group**：枢轴在肩/腰（衣物的真实悬挂点），不在底边；
   `geometry.translate` 把几何体移到枢轴下方，rotation 留给外层驱动（风摆+臂推）。
   襟片被手臂顶开是合法解，预留接口比拍摄期补铰链便宜一个数量级。
3. **穿戴件（背带/包/耳返）建造期即定挂点净空**：挂点选躯干低活动区（胯侧/肩后），
   按 worn_prop 探针口径预留——贴体软接触（<2cm）合法，深穿报错；背带两端都必须
   连得上（肩点→包顶连接件），断带是建造缺陷不是拍摄问题。
4. **建造验收第一天接探针**：新角色出道前必须跑通建造期探针——limbBody 躯干环列
   嵌入/肘凸（elbEx）/翼角、rest_support 可达性（坐姿肩-大腿面距离 vs 臂长，
   臂短体型"平放大腿上"物理不可达，直接排除该静息姿势）、穿戴件 worn_prop。
   拍完再补=把类目留给用户复看（S1E3 八轮串行枚举实录）。
5. 数值口径全部指回
   [direct-animation-craft/references/contact-and-hands.md](../direct-animation-craft/references/contact-and-hands.md)
   （嵌入平阈/肘极混合/襟片臂推/穿戴件净空），此处不抄表；换装型要重测环列半径
   （外套比贴身穿衣宽出的量进 TORSO_RINGS，否则探针把外套厚度当嵌入）。

## 动漫化形象清单

形象"不像动画片"时按此清单逐项核对（bio_armor_academy_s1e2 R21 复看确认的形象层缺口）：

1. **表情符号化** —— 汗滴/爆筋/眼白/豆豆眼/黑线脸/脸红斜线等动漫符号的语义表、
   canvas/billboard 绘制配方与弹入-停留-退场时序，见
   [references/anime-expression-symbols.md](references/anime-expression-symbols.md)。
   纪律：符号由情绪事件驱动、不常驻，同屏同角色不超过 2 种。
2. **夸张表情拓扑** —— 嘴占半脸、掉下巴、整眼替换为符号形的分支画法
   （canvas 工艺换绘制分支，3D mesh 眼工艺切换预建模形），见同上文件末节。
3. **统一赛璐璐材质** —— 全角色共享 toon ramp（阴影阶偏冷偏紫、不用纯灰），
   不混搭 Basic/Lambert/Phong 三种光照模型；高光件限同色系小面积或改假高光贴图。
   配方见 [references/modeling-techniques.md](references/modeling-techniques.md) 第 9 节。
4. **全身描边分级** —— 法线外扩壳从头发推广到躯干/四肢/装备，
   线宽分级：轮廓主干 > 四肢 > 细节；凹面内漏风险见
   [references/handdrawn-style.md](references/handdrawn-style.md)。
5. **阴影统一** —— 硬切 cel 阴影优先；日落逆光场景保留软阴影时压淡到 0.4–0.6。

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
- Leg/sock/shoe junction reads as broken → inspect parent/local transforms, visible gaps, occlusion and nested outline hulls separately. Parts under one group already share its transform. The episode's coaxial boot capsule was a local seam workaround, not a final footwear standard; preserve a readable instep, toe, heel and sole, and use ankle/contact controls when required. Update parts before generating their outlines.
- Nested part's sketch hull pokes through the enclosing mesh (sock hull jags out of the shoe = "fracture line") → strip the inner part's strokes (remove its `userData.stroke`/`userData.sketchLine` children) or let the outer part fully cover the junction.
- Mirrored pair angles written as `value * side` → one side fans/flips wrong (Mochi's left whiskers fanned upward): sanity-check the `-1` side by hand; sign errors survive every screenshot until someone looks at a close-up.
- Spikes/tufts sized to sit exactly flush with a hair/shell surface get swallowed by it (Dodo's hair spikes: tip == cap top → invisible): size signature protrusions so tips clear the enclosing shell by a visible margin, then confirm from a front close-up.

## 踩坑记录

- **脸贴片翻车三连（2026-10-07 bio_armor_academy_s1e2）**：①脸贴覆盖角必须匹配
  角色 yaw 朝向与机位扇区——贴片只盖正面 ±36° 而角色面朝 +x、机位在 +z 时
  看到的全是侧后脑（"看不到脸"≠"脸没画"，先查朝向再查贴图）；②球段坐标贴片
  半径要比颅骨大一圈才不露馅；③逆光/黄昏场景脸贴用 MeshBasicMaterial
  （Toon 正面全黑）。本集把脸贴加宽到 ±65° 解决。
- **挂在肢体上的甲片/配件尺寸不得超出肢体实际长度（同上）**：前臂肘→腕仅
  ~0.18m，分段甲排到 0.2 就溢出手腕悬空——按 twoBone 骨长排布配件。
- **脸贴片的下一步：参数化雕刻头（2026-10-08 S1E2 R2）**：贴片加宽只能救正面
  扇区；要侧脸/3/4 机位可读，用 levels 轮廓车削出头型（下颌/颧骨/颅顶逐圈收放，
  鼻凸用高斯项局部挤出），脸不再是贴片而是画在头型 UV 上的 1024 canvas 纹理
  （正脸占 UV 中段，侧后区 UV 收到边缘窄条防止拉伸）。眨眼画成"眼皮从上往下
  盖住固定虹膜"，**不要**把整眼纵向压扁（压扁读成眯眼不是眨眼）。纹理按
  `kind/emotion/量化blink` 缓存复用，key 变化才重建，否则每帧建 canvas 会卡。
- **表情/手势要沿条目边界插值**：fist/open/point、headYaw 等离散语义参数也要进
  边界 0.3s 混合列表，否则换条目时手型瞬切穿帮；表演谱里 blink 字段（如闭眼
  硬扛）要优先于自动眨眼。下蹲/坐下时肩点必须跟 hipY 联动（torsoOffset），
  否则蹲防时手臂悬空脱离躯干。
- **爪/角等端部配件挂指骨末节，不写死手部局部坐标**：手指弯曲时写死位置的
  爪尖会悬浮；挂到 `chain.bones.at(-1)` 上随指形走。
- **共享材质缓存上不能挂独态发光（2026-10-09 S1E2 R14）**：craft 系 `mat()`
  按颜色字符串缓存共享——给某个部件加 emissive 脉动前必须 `.clone()` 或新建
  材质，否则同色部件全被染色（拳甲锤头的熔光一度会染到同色甲段）。
- **黄昏逆光下暗色小尺寸特效件直接消失**：碎石/甲片等暗色小件在夕阳逆光里
  读成一团黑，需要独立材质 + 余热/能量 emissive 才能成立；加色混合
  （AdditiveBlending）发光件不受影响。
- **生长/变身特效要纯 (t,state) 确定函数**：生长环、拼合粒子等只能由当前时间和
  状态参数推导（不能记"上次状态"区分生长/碎裂），否则 seek 校验必翻车；
  方向性语义（生长 vs 碎裂）从谱面 phase 显式传入。
- **脸部体积不能靠固定色斑代替（S1E2 R15→R19 用户复看）**：早期增加额头和
  双颊阴影的尝试被指出“一片一片”，后续统一脸、耳、颈、手的肤色并取消硬色块。
  先检查脸型、五官和实际镜头尺寸，再决定轻量阴影；细节与明暗不是越多越好。
- **发际线/发茬画进脸纹理，不做 3D 小件**：3D 碎茬管会悬浮在额皮上读成
  刻度线；画进纹理贴曲面零深度问题。但要先算发壳边缘在纹理 canvas 的
  落点（本集为 v=(y+.07)/.287 → 像素 y=(1-v)*512；换头型需重算），放错行会被发壳整个盖住。
- **短发与假发感（R20）**：后脑、耳后和后颈的覆盖与体积先成立，再组织贴合的
  发束；散乱短茬和悬浮细管不能代替发型设计。五视图与头部俯仰检查见
  [人物造型样板](../direct-animation-craft/references/character-look-development.md)。
- **直管躯干不像人（2026-10-09 S1E2 R18）**：ringsGeometry 躯干断面要有人体
  节奏——骨盆（衔接腿根）→ 收腰 → 胸扩 → 肩斜（斜方肌收窄）→ 颈根小圈；
  等宽椭圆管正面读成纸板。早期独立肩球在 R19 改为袖根接入胸廓，避免球形接头；
  腿部按大腿、膝、小腿和踝安排粗细变化，段数不能替代实际轮廓检查。
  外套类轮廓件要包住新胸廓（胸宽过背板会从侧面穿出）。
- **走路上身必须接入实际变换（R18→R21）**：重心侧摆后重新换算脚部局部坐标，
  躯干、肩根和手目标共用变换，头部按表演适量稳定。起停、转身与最后收脚共同
  设计，不能只在旧步态上叠正弦摆动；具体工艺归 walk-director。
