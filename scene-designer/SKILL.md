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

- 宫门后仍透出天空时，检查真实门洞、侧壁、顶板和后墙。深色面片不能代替有深度的
  遮挡；用正面和斜机位的穿门射线确认命中内殿实体，并复查新增墙体是否挡住结尾镜头。
- 入退场穿环境且角色检查已过时，沿用
  [环境路径覆盖复盘](../direct-animation-craft/references/environment-path-audit.md)。
  `cameraObstacles` 不自动等于人物碰撞；contract 必须有实际消费它的运行检查。

- For an accepted text-to-image background plus interactive 3D geometry, keep [hybrid-craft-scene](../hybrid-craft-scene/SKILL.md). A successful character generation trial is not a reason to rebuild the location.
- If a specific prop or building needs a generated mesh, use [build-image-to-3d](../build-image-to-3d/SKILL.md) for that asset, then validate scene scale, walkability, camera coverage and contacts here. A single room image does not establish a complete navigable room.

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
- 可交互物（门、桌、道具、矮沿）必须定义碰撞代理与交互净空区；角色-场景接触的数值断言与最小距离表见 [direct-animation-craft/references/contact-and-hands.md](../direct-animation-craft/references/contact-and-hands.md)。
- 可通行的门必须有真实门洞，不能在实心墙盒表面只贴一扇活动门。出门路径覆盖门槛、门框外全身净空和绕墙角；开门、回弹、关门都检查全身与携物，代理取实际几何和最终变换。S1E3 P6 的漏检与修复见上述接触文档。
- `build()` runs before characters are added. Async assets must expose a scene `readyPromise` consumed by the renderer.

## 踩坑记录

- **实景改造方法论（2026-10-07 yuki_airport_t2 长乐机场 T2）**：先拿实景照片提取
  "签名特征"（本集：木色条板波浪吊顶 + 白色喇叭口天窗阵列 + 白色几字形马鞍脊梁 +
  灰底橙红叶纹地毯），Q 版积木抓住签名特征即"像"；特征间冲突时按实景分区
  （喇叭口在出发大厅、马鞍脊梁在指廊，同轴冲突就分区摆放）。
- **NoToneMapping 下纯白无层次**：白色雕塑壳/膜结构要压灰一号（如 #ece7dc），
  否则糊成无细节的亮块；发光片半径须略小于其膜口沿（本集 1.42 vs 1.55）防露边。
- **竖屏横向视野极窄**：720×1280 下 fov40 的横场角只有约 ±12°——双角色同框要么
  同深度靠近站，要么相机沿纵深退远；侧向拉开的双人构图必然裁人。
- **白色/浅色物体在亮背景前的轮廓陷阱**：白色机身侧对亮天空时只剩彩色尾翼可读，
  会读成悬浮异物；剪影类配景要么压深色、要么给全轮廓角度。
- **机械剪影要拿"特征轮廓三件套"（2026-10-08 S1E2 R3 塔吊）**：单个实心柱+
  几片旋转横板堆出来的塔吊读成"带刺柱子"；可读塔吊=格构塔身（四角柱+交叉
  斜撑）+ 臂架伸进画面上空 + 塔尖斜拉索三角 + 吊绳吊钩。剪影物体的验收标准
  是"一眼能叫出名字"。
- **贴地半透明片（积水/水洼）防"发光飞碟"**：线性渐变+硬边圆+高不透明度会
  读成悬浮发光盘；用径向羽化 alpha 边缘 + 整体压暗（opacity≤.5）+
  depthWrite:false。注意 update() 里的呼吸动效别覆盖 build 的低调设计
  （本集 update 把 opacity 写成 .78，把羽化片又变回亮碟）。

- **浏览器 probe 脚本的 /tmp 路径坑（2026-10-07 bio_armor_academy_s1e2）**：Git Bash
  的 /tmp 与原生 Windows Python 的 /tmp 解析不同——probe 脚本放 episode tmp/ 或
  仓库根，别用 /tmp 中转，否则 bash 建的文件 Python 找不到。
- **改成各宫独立故事要更换空间机制**（2026-10-19）：重命名旧总坛或换背景
  不能满足“各自地盘”。为本宫设置独立路径、地形签名、生活用途和关键交互物，
  同步更新演员实例化名单与系列分集安排；旧全员群战入口保留作历史文件。
- **viewer 编译事件与 SceneBase 回调分开声明**：`Beat/Cue/Act` 可能由单集编译器
  生成配置后被 viewer 消费，不能为了让通用 scene_tool 转绿而添加无效回调。
  保存编译器、产物、消费入口映射；运行 JSON Schema、story catalog、全时间轴
  viewer 检查，并明确通用回调验证尚未覆盖这一模式。不可把 schema 通过写成
  scene_tool 全项通过。
