# 3D 管线（.story DSL）的走路镜头

适用：`dula-engine` Storyboard + 低模角色的剧集（doraemon_air_cannon、
hurdles_championship 等）。2D 关键帧管线看 keyframe-walk-shots.md。

## 最小可用写法

```
[Girl]{Event:Move|character=Girl|x=5|z=0|duration=6}{Camera:FollowCharacter|target=Girl|offset=0,1.5,4|lookAtOffset=0,1,0}
```

- `{Event:Move}` 由 `Storyboard.js:777-800` 处理，**自动并播 Walk 动画**
  （`Storyboard.js:796`，`ev.action || 'Walk'`），不用手写 `{Anim:Walk}`。
- 位移由 `CharacterBase.moveTo()`（`dula-engine/characters/CharacterBase.js:306-313`）
  执行：x/z 线性插值，移动中自动朝行进方向转身（`:501`）。
- Walk 动画（`dula-assets/animations/common/Walk.js`）是**原地循环，无 root
  motion**（`Walk.js:67-70` 只有 y 起伏和前倾）——位移全部来自 `moveTo`。

## 步速匹配（防滑步）

`moveTo` 的位移速度与 Walk 的步频/步幅**没有任何耦合**，不匹配就滑步。
默认参数 `stride=0.42`、`frequency=1.9` 步/s ⇒ 视觉步速约
`stride × frequency ≈ 0.8 m/s`。

给定镜头后按公式对齐两边：

```
目标速度 v = 移动距离 / duration
Walk frequency = v / stride      （stride 默认 0.42）
```

例：6s 走 5m ⇒ v≈0.83 ⇒ frequency≈2.0。需要变速走（快走/踱步）时同步改
`frequency`，不要只改 `duration`。

## 步态风格（gait persona）

Walk 的六个参数就是"走相"的全部旋钮（`Walk.js:34-46`）。DSL 里直接写在
`Event:Move` 标签上——tag 参数整体经 `ev.options` 透传给 Walk 构造函数
（`Storyboard.js:337,799`）：

```
[Granny]{Event:Move|character=Granny|x=2|z=0|duration=8|frequency=1.2|stride=0.22|legLift=low|armSwing=0.1|bodyBob=0.02|lean=0.1}
```

| 参数 | 默认 | 控制什么 |
|------|------|----------|
| `frequency` | 1.9 | 步频（步/秒），别名 cadence/stepsPerSecond |
| `stride` | 0.42 | 步幅（髋摆角），别名 strideLength/legSwing |
| `legLift` | 0.28 | 抬膝高度；命名档 `low`=0.16 / `mid`=0.28 / `high`=0.42 |
| `armSwing` | 0.28 | 摆臂幅度 |
| `bodyBob` | 0.035 | 身体上下起伏 |
| `lean` | 0.035 | 前倾角 |

常用 persona 起手值（拍完按观感微调，别一次到位）：

| persona | frequency | stride | legLift | armSwing | bodyBob | lean | 特征 |
|---------|-----------|--------|---------|----------|---------|------|------|
| 少女轻快 | 2.0–2.2 | 0.42–0.5 | mid–high | 0.3–0.4 | 0.04–0.05 | 0.03 | 步频快、有弹性 |
| 老奶奶蹒跚 | 1.1–1.3 | 0.18–0.25 | low | 0.1 | 0.02 | 0.08–0.12 | 小步拖行、驼背前倾 |
| 疲惫拖沓 | 1.3–1.5 | 0.3 | low | 0.15 | 0.025 | 0.06–0.09 | 慢、沉、略驼 |
| 赶路快走 | 2.4–2.8 | 0.5–0.58 | high | 0.4–0.5 | 0.045 | 0.05–0.08 | 接近跑的走 |

两条纪律：

- **改 persona 后必须重算 duration**：v = stride × frequency。老奶奶
  0.22 × 1.2 ≈ 0.26 m/s，走 2m 要 ~8s；给 3s 就是滑行。
- Walk 的 `suits` 标签限定 humanoid/fighter/athletic、身高 0.8–2.5
  （`Walk.js:29-32`）；圆胖/四足角色套不上，哆啦A梦有专属 `WaddleWalk`。

## 跟走运镜选型

| 运镜 | 来源 | 平滑 | 适用 |
|------|------|------|------|
| `FollowCharacter` | assets/camera/common | 无（硬贴位置+lookAt） | 远景全身，快速可用 |
| `TrackingCloseUp` | assets/camera/common | 低通滤波 cutoff=8 | 跟头部特写 |
| `FightFollow` | assets/camera/fight | lerp smoothness | 锁侧面轴线的横向移动 |
| `RaceSideTrack` | assets/camera | 侧面平行 | 多名角色同向奔跑（跨栏集实测） |

DSL 语法 `{Camera:Name|key=value}`，数组逗号分隔；每个条目只取第一个
Camera 标签（`StoryParser.js:199-201`）。

**缺口**：没有"带平滑的通用全身 follow"。需要时把下面的模板复制进剧集
`bootstrap.js` 注册（模式抄 `FightFollow.js:33-41` 的 lerp +
`FollowCharacter.js:16-30` 的自由 offset）：

```javascript
import { CameraMoveBase } from "dula-engine/camera/CameraMoveBase.js";

class WalkFollowSmooth extends CameraMoveBase {
  constructor(params = {}) {
    super(params);
    this.target = params.target;
    this.offset = params.offset || [0, 1.6, 4.5];      // 相对角色的机位偏移
    this.lookAtOffset = params.lookAtOffset || [0, 1.0, 0];
    this.smoothness = params.smoothness ?? 4.0;         // 越大越紧
    this._desired = null;
  }
  update(progress, camera, context) {
    const mesh = context.characters.get(this.target)?.mesh;
    if (!mesh) return;
    const p = mesh.position;
    const desired = new THREE.Vector3(
      p.x + this.offset[0], p.y + this.offset[1], p.z + this.offset[2]);
    if (!this._desired) this._desired = desired.clone();
    const dt = 1 / 60;
    this._desired.lerp(desired, 1 - Math.exp(-this.smoothness * dt));
    camera.position.copy(this._desired);
    camera.lookAt(p.x + this.lookAtOffset[0], p.y + this.lookAtOffset[1],
                  p.z + this.lookAtOffset[2]);
  }
}
// bootstrap.js: registerCameraMove("WalkFollowSmooth", WalkFollowSmooth);
```

（`THREE` 的导入方式以对齐同剧集 bootstrap.js 里现有自定义类的写法为准。）

## 方向与朝向

- `moveTo` 自动转向行进方向。需要**侧向行走**（角色面朝镜头、横向平移，
  阅兵式镜头）时，行进后另给 `face` 参数或单独控制朝向，并接受这种拍法
  步态与移动方向不一致的代价。
- 入场/出场可以用场景切换的自动 walk-out/walk-in（`Storyboard.js:718-765`），
  不必手排。

## 成功案例

- `doraemon_air_cannon/script.story:108`：Event:Move + FollowCharacter。
- `yuki_cat_diet/script.story:179`：同上。
- `hurdles_championship/script.story:170`：RaceSideTrack 侧跟多名跑者。
