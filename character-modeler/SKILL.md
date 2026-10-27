---
name: character-modeler
description: Design, build, and integrate distinct animatable Dula characters using procedural Three.js geometry or generated 3D meshes. Own character identity, silhouette, rig and face integration, and deformation review; route Tripo and image-to-mesh generation through build-image-to-3d.
---

# Character Modeler

Create a distinct character that can perform in the selected Dula runtime. Choose procedural geometry, generated meshes, or a combination based on the requested appearance and deformation needs. The existing procedural workflow below composes Three.js shapes and an animatable face; it does not prohibit imported models or textures on other routes.

Keep the skill in `dula-skills/character-modeler/`. New characters live in `dula-assets/characters/<Name>.js` and are registered in `dula-assets/index.js`.

## Choose the construction route

- Keep one character entrypoint with separate head and body references. Head identity, facial projections and hair use the existing appearance references below; reusing a rigged body or changing wardrobe uses [Body reuse and wardrobe adaptation](references/body-reuse-and-wardrobe.md). Join them for head/body proportion, neck/shoulder/collar connections and final-shot style review.
- Motion remains owned by [direct-animation-craft](../direct-animation-craft/SKILL.md) and its walk/contact references: the character supplies geometry, bind axes, deformation and contact anchors; the episode supplies acting and timing. A bad motion mapping is not by itself a reason to rebuild an accepted body.
- For an existing procedural character, retain its working performance and improve the relevant silhouette, anatomy, face or material; use the workflow below.
- For text-to-image followed by Tripo or another image-to-mesh backend, use [build-image-to-3d](../build-image-to-3d/SKILL.md). This skill still owns the character design and acceptance. Skip primitive-only construction instructions for an imported mesh.
- For continuous limbs, joint deformation and shot-specific correction, use [direct-animation-craft](../direct-animation-craft/SKILL.md). A static attractive model is not proof of a usable speaking character.
- For armor that reads as folded paper, disconnected plates or disappears from behind, read [animated metal armor](../hybrid-craft-scene/references/animated-metal-armor.md): distinguish reflection from wraparound volume, inspect inner walls and rims, fit belts to the actual waist, and retain working joint and equipment anchors.
- Identify the real integration target first: `CharacterBase` or an episode's self-contained viewer. Preserve the selected target's pose, face, readiness and equipment contracts.

For a generated candidate, review front/side/back and hands, hair and clothing separation; then test one line with gaze change, an arm lift or grasp, and a step. Report static appearance, rig presence, deformation and face support separately. Do not replace an accepted environment as a side effect of changing a character.

When adapting an accepted procedural character, inspect its final appearance
composition, not just its base class. If custom shading uses `onBeforeCompile`
and `customProgramCacheKey`, verify those hooks after cloning a material for a
new palette. A copied color can silently lose the accepted shading; compare the
actual head and hair at the same camera before extending the change.

For a textured imported face that blinks and speaks but still feels lifeless, read
[Imported face performance](references/imported-face-performance.md). Separate acting timing
from rig limitations, and compare a short dialogue shot before extending the change to an episode.

## Drawing Methods

This workflow has two existing looks. Follow the user's established choice; clarify only when an unresolved style choice materially changes the work:

1. **Clean toon mode** (default) — smooth shapes, `MeshToonMaterial`, no line work. Matches all existing characters.
2. **Hand-drawn sketch mode** — the same geometry, plus wobbly ink outlines, overshoot detail strokes, and 12 fps "boiling" via `sketchify()` + `BoilSystem`. Read [references/handdrawn-style.md](references/handdrawn-style.md) before using it. Sketch mode is opt-in per character (subclass + register, or apply in an episode bootstrap) — never retrofit it onto existing characters without being asked.

## Boundaries

- For the primitive-only task this skill describes, use Three.js primitives (Sphere/Capsule/Cylinder/Box/Cone/Torus/Tube/Lathe) composed in code. If that representation cannot meet the requested silhouette or deformation, explain the limitation and follow the production route above instead of treating this constraint as universal.
- Match the look of existing characters: `MeshToonMaterial` + 4-step canvas gradient. Do not introduce new shading styles (PBR, custom shaders) unless the user asks.
- For the `CharacterBase` route, follow its contract exactly: animation, lip-sync, expression and combat read specific fields. Read `dula-engine/characters/CharacterBase.js` and a reference character before implementation. A self-contained viewer instead follows its actual pose, face and loading contracts.
- Never claim the character looks right until you have rendered screenshots via `dula-verify` and inspected them.
- If the user explicitly requests no visual inspection, follow that constraint. Use bounded poses and numeric geometry checks, deliver a video for the user's review, and describe the character's appearance as unreviewed. Do not treat numeric clearance as artistic approval.

## Load Context

- 耳朵像白色饰件、同心环或贴纸，读
  [耳廓简化与头部连接](references/drawn-ear-study.md)。先看耳的朝向、耳根和
  脸部肤色，再决定结构线；不要以“耳朵可见”代替结构正确。

- 头发像粗管、厚叶片或头套，或用户要求上网学习绘制技巧时，读
  [图形化发型学习与试样](references/layered-hair-study.md)。先核对轮廓、发流、
  分层与底壳覆盖，再实现；薄片、细发丝或两档明暗本身都不保证造型改善。

- 需要主动发现角色问题或用户反复补漏时，先用
  [character-attention-review](../character-attention-review/SKILL.md) 组织维度、
  证据覆盖与漏检回测；以下人物审美参考提供结构关系和具体历史案例。
- 用户要求人物更好看、更像原画或积累审美经验时，先读
  [人物审美判断](references/character-aesthetics.md)：先执行其中“多维度问题发现”，
  用独立原画与当前整图列出主要差距、证据、可见范围和优先级，再决定修什么。
  不能从自己熟悉的参数、刚改过的部位或某个候选方案反推问题清单。
  解释目标为何成立、当前差在哪里，
  按其中“由大到小的关系对照”先看整体、再看相邻结构及遮挡、最后看局部，
  同时检查修正不足与修正过量；之后再选实现方法。打开过图片不等于完成全图检查。
  算法辅助定位与回归，大模型判断整体身份、气质和结构关系；局部检查后返回
  正常观看大小的完整头像。用户认可的视图先设为保留基准，不随新局部修订重塑。
  **问题发现先于分解对比，分解对比是必经步骤**：先做任务范围内的完整区域检查，
  后脑/耳后/后颈不可由正面刘海对照代替；未见、未查与无明显问题分开记录。
  再按该文“分解验证的交付门槛”实际生成并查看参考/保留基准/
  当前候选的受影响部位对照，逐项记录，再做整脸和连续转面复查。只有整图、算法报告
  或已阅读skill，不算执行了该流程；没有这些证据不得报告角色一致性通过。
  拆图前先核对参考的头身方向、俯仰、侧倾和发型侧别，并查历史选图结论；不能将
  同一张姿态不同的九宫格画稿反复用作多个标称角度的精确造型依据。
- 用户要求角色接近文生图、把三维角色渲染成二维画风，或希望像混合场景一样让
  生成图直接贡献成片细节时，读 [生成绘画直接用于角色](references/generated-character-paint.md)。
  原始已确认绘画是美术目标；程序截图不能充当独立参考来证明还原成功。
- 曲面绘画出现面具感、聊天与唱跳角色不统一，或裙壳随动作脱节时，读
  [晴印三维舞蹈修订](references/sunprint-dance-revision.md)：沿实际头面、髋膝和
  表演实例定位问题。用户已授权自由选择工艺时，以最终融合效果决策，不再把
  自绘或映射等技术选择交还用户；技术采样通过与用户美术认可分别记录。
- 正面接近原画而 45°/65° 失真，或要把审美判断变成可重复工艺时，读
  [多视角拟合与失败复盘](references/multiview-character-fit.md)。先分清几何、
  UV、分层和遮挡问题；单张 90° 漂亮不能证明连续转面成立。70°—90°换脸感、
  裸头与带发不一致、耳发修改牵连正面时，读该文末的连续眼颊边界与耳发修订记录。
  近眼偏圆时参照其“近眼投影与虹膜包裹”复盘；已获授权按角度并行修订时，执行
  “并行角度候选的合并验证”，冻结候选源码后重新检查组合效果。
- 用户希望沿用小雪 craft3d 的二维观感，或将生成网格与手绘工艺融合时，读
  [曲面角色与绘制外观](references/craft3d-drawn-characters.md)：连续造型、曲面五官、
  主发束、全身色块与生成前约束；区分造型方法和某个历史角色的验收状态。

- Read [references/modeling-techniques.md](references/modeling-techniques.md) for the collected Three.js hand-modeling techniques (primitive sculpting, toon shading, outline, pivots, face construction, proportions).
- Read [references/handdrawn-style.md](references/handdrawn-style.md) for sketch mode (ink strokes, sketchify, boiling) when the user wants a hand-drawn look.
- Read [references/characterbase-contract.md](references/characterbase-contract.md) for the exact fields the engine expects.
- Read [references/anime-expression-symbols.md](references/anime-expression-symbols.md) 动漫表情符号化：汗滴/爆筋/豆豆眼/黑线脸等符号的语义表、绘制配方、触发纪律与夸张表情拓扑。
- Read `dula-assets/characters/Doraemon.js` (round cute) and one humanoid (e.g. `Zorak.js`) as working code references.
- 可执行积木：`dula-assets/lib/craft3d/`（surface/hand/pose/look/locomotion）是本 skill 造型工艺的共享代码形态；已验收的完整角色参考 `dula-assets/characters/bioarmor/`（《9章》系列）。新角色优先基于这些积木搭建，不要从 episode 目录拷贝。
- `characters/bioarmor/QianTangKuiCraft.js` 的 S1E4 R1 曾因复用雷晓脸型和比例被用户否决；
  R2 为独立下颌/眼形/肩腰/身高的数值试验，仍非美术验收样例。新人物须在形状与表演上
  可区分，不能只换头发和颜色。不要让“共享已验收资产”误写成“其中所有新角色已验收”。
  真实袖/手对躯干探针在
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

- Imported textured faces: separating iris motion, eyelids, brows and lips is necessary but not sufficient
  for expressive acting. The S1E4 first dialogue preview was rejected for lifeless eyes despite blinking
  and mouth movement. Review listener reactions and gaze intent in the actual shot, not just rig controls.
- Painting over an old iris with sampled white produced duplicate rims; a continuous local texture warp
  pinned at the eyelid boundary reduced that artifact. It remains a limited frontal graphic rig, not
  independent eyeball geometry or a recovered anatomical face. Strong turns and large emotions need
  separate validation. Small authored morphs must not be described as a complete ARKit facial rig.
- Imported garment repair must isolate cloth. A bind-space bounding box can also contain the forearm;
  filtering its influences to hips creates torn-looking skin. In the current stylized Aoi, restricting
  the correction by dark albedo separated skirt from skin, but this palette-specific fix is not universal.

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

- **发型加件的材质工艺必须与底发一致（2026-10-18 stardust_clad_op R8 阿箸）**：
  animatedHead（bioarmor 正本）底发是 unlit `MeshBasicMaterial` 顶点色；episode 侧
  加发壳/发缕时若用 toon 材质深色件，夜景阴影里读成纯黑"眼罩带"，与底发撕成两截。
  加件用同工艺 Basic + 同色阶（底发 #503a3b→#423037 渐变，加件 #47343a/#3a2b31）
  即融合；发色想压黑也要跟着底发色阶走，不要直接上 #17 级纯黑。
- **新角色辨识度（2026-10-14 S1E4）**：独立参数表并不证明画面能区分角色。
  用户再次否决女主与男主过像后，实际同时改了下颌/眼形、长发外轮廓、领口和裙装，
  并在原机位双人画面复核。共享绑定可以保留；角色设计不能仅靠换色或小幅缩放。
  镜像领片时同步翻三角绕序，否则其中一侧会露出背面描边而变成黑片。

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
- **ringsGeometry 环列 y 必须升序（2026-11 borrowed_moonlight P2）**：裙摆环列从腰到膝
  按降序写（[.80…]→[.32…]）→ 三角绕序翻转、法线朝内，整件裙子只吃 toon ramp 阴影阶
  （米白裙渲成深紫灰），BackSide 描边壳跟着翻面。环列永远自下而上排列再检查法线。
- **pose spec 漏字段=整头静默消失（同轮）**：headYaw/headPitch 未在 spec 兜底时
  `headGroup.rotation.set(undefined,…)` → matrixWorld 全 NaN，头部子树整体不渲染但
  无脚本异常（shape-and-deformation「pivot 字段 NaN」的姊妹篇；几何/纹理/可见性探针
  全部正常，只有 localToWorld 出 NaN 才现形）。求解器出口一律 `??0` 兜底。
  外套类轮廓件要包住新胸廓（胸宽过背板会从侧面穿出）。
- **走路上身必须接入实际变换（R18→R21）**：重心侧摆后重新换算脚部局部坐标，
  躯干、肩根和手目标共用变换，头部按表演适量稳定。起停、转身与最后收脚共同
  设计，不能只在旧步态上叠正弦摆动；具体工艺归 walk-director。

## 铠甲/穿戴件贴身纪律（2026-10-18《星屑战壳》R2.6）

- **禁止悬浮环**：腰甲/腿甲/臂甲不能做"离体光环上挂甲片"。腰带=贴髋部断面的
  椭圆环带；甲叶铰接腰带下沿，内面与大腿保持 5~10mm，随大腿姿态纯函数摆动
  （站立贴腿下垂、抬腿被顶起外撇）；膝甲贴膝点、胫甲半径=实测腿管半径+间隙
  （写死半径必嵌入）；胸甲=胸廓剖面整筒；肩甲锚三角肌盖随肩点+上臂根方向。
- **clad_fit 探针**：甲片内面与身体距离 ∈[3mm,25mm]，悬空/嵌入即报警；
  度量"平板搭圆管"要用骨轴→甲片内面平面的垂直净空（轴心距-管半径会误报），
  探针窗口避开非中性姿态（定格悬空收腿会误判）。
- **华丽铠甲关键词**（监制参考口径）：上扬翻卷壳状肩甲、额饰头冠、圆形纹章+
  V 形棱线收束、全覆盖臂/腿甲分段环纹、披风（分段网格纯 (t,lift) 摆动）。
- **脸谱差异化**：共用头脸正本时按角色做参数包（眼宽高/眼距/眉形/嘴型/脸型
  剖面/发型件/肤色板），验收标准是"只看剪影和脸就分得清"。
- **展示型道具朝向别绑手部 IK 轴**（R5 权杖教训）：握点（接触）绑手心、朝向
  （读感）独立定型（固定 Euler+纯 t 微晃），探针只测接触点。道具面相主镜头，
  小件道具要放大到读感尺寸（铲面≈肩宽 1/3）否则远景读成细棍。
- **圣衣区别要进入结构与剧情**（2026-10-19 守宫重制）：换色和胸口宝石不足以
  区分角色。先分叠甲轮廓、左右对称性、护具功能，再补铆钉与刻纹；导火鳍、
  收链棘轮等功能件要在使用和损坏镜头中兑现。已有骨架的局部精修使用显式
  opt-in 配件，避免默默改变所有旧集。参考 `characters/stardust/palace-clad.js`。
- **叠甲描线不能共面**：新增肩甲两层若共用相同前表面深度，会闪成横条；
  甲面与描线分别保留层间深度。检查实际近景，增加多边形数量不能消除 z-fighting。
- **表情默认值须显式复位**：角色构造器的 smile 等 acting 参数可能不被
  setEmotion 覆盖；战斗和受伤镜头必须同时设置 smile/focus/fear，不能只换情绪标签。
