# 绘画空间与最终接触时钟

## 使用场景

3D 底稿和独立绘制的场景不是同一台摄影机。人物落在屋顶、比门高几倍、站上桌面时，
先修坐标、透视比例和前后遮挡。把脚底钳到一条地面线只能改高度，不能同时修复深度、
大小、画中的门和台阶。不可因旧投影 probe 全绿而认定场景融合成立。

## 共享执行件

- `assets/painted-space.js`：底图原生像素相机、画幅覆盖限制、人物路径、有限步数与
  起停、同一时钟的触地表、接触影。当前默认底图 1920×1080；其他尺寸先明确适配。
- `assets/painted-weather.js`：绝对时钟的分层雪/花瓣/微尘、绘画云层移动、局部光晕。
  建筑遮挡区域和灯具位置仍须按剧集绘画标定。相机追踪和景深不是全自动恢复。
- `assets/painted-particles.js`：沿用原 3D 粒子轨迹、寿命和颜色，投影锚重注册到绘画
  道具或人物；柔边 sprite 与尺寸限制。剧集用稳定语义 ID（或固定 seed）绑定，
  不按粒子数量猜系统，数量会撞车。
- `../walk-director/scripts/export_painted_contacts.mjs`：从最终路径导出触地表供 Foley。
- `scripts/contact_sheet.py`：带时间标签的逐镜检查表；脸和发缘仍需原生裁区检查。
- `scripts/split_pose_atlas.py`：规则网格原画的透明裁切与边距配准。`--sequence` 可显式
  声明持帧顺序；四张原画展开为八格曝光仍是四张独立姿势，不写成八张过渡画。
- `scripts/replace_windows.py`：多段不重叠窗口的一次整片拼接，保留完整源音轨，验证
  每段边界、帧数、渲染指纹和 seek 报告，避免为一轮局部姿势返修反复重编码整片。

```js
const shot = {
  start: 12, end: 18,
  camera: {from: [960, 700, 1.8], to: [980, 710, 2]},
  actors: {child: {
    cel: 'walk', at: [1200, 1000, 260], to: [980, 800, 70],
    walk: {start: 12.2, end: 17.7, steps: 8}
  }}
};
const camera = paintedCamera(shot.camera, t, shot.start, shot.end);
const actor = actorInPlate(shot.actors.child, t, shot.start, shot.end, camera);
```

`at/to/path` 的三项是底图中的 x、接触 y、人物高度。`screen:true` 显式声明肖像和
道具插入镜头，免于误套场景地面。相机覆盖修正必须作用到同一个 camera，再由所有
人物、窗光、门、脚印共用，不能只移背景导致相对滑动。

## 必须由导演完成的内容

1. 在原图标门槛、桌面、地面、椅面、台阶等可见支撑面；按门高与邻近物体复核人高。
2. 桌后的人脚在桌后地面，桌面和桌前沿盖住腿。阴影不能替代遮挡；只盖脚而留下
   整条小腿仍像站在桌上。
3. 步态画至少有两侧支撑和中间相；统一持物手，检查披风与裙摆变化。有限步数控制
   只是步相时钟，不是鞋底无滑移求解器；实际鞋底与重心必须看片段。
4. 用最终 cel 的灯芯/手/眼坐标接效果。3D 灯芯照到脸颊、泪光落鼻头、文字飘出画面，
   都是重注册缺失，不能通过扩大辉光掩饰。
5. 情节会形成或消失的物件不能永远画在底图里。准备 clean plate，按原剧情事件显现；
   形成前、形成后、离开后均抽帧。清理底图使用当前允许的图像编辑通道。

## 验收与失效

先出全镜表关键帧再渲整集，避免只修走路忘了特写露边。最低检查包括画幅四边、
实际人物 alpha 可见范围、遮挡后下缘、道具锚、同机位的相位序列、随机 seek 一致。
最终渲染前记录本次使用的配置、原画、运行模块指纹；代码或原画改变须重新出受影响镜头。

数值正确只说明摆放执行符合配置。配置本身是否符合透视、是否像自然表演，由主代理
查看实际画面判断。旧坐标系统的地面 probe 在切换管线后必须删除或明确停用。

## 多窗口返修配置

`replace_windows.py --episode <episode> --config <json>` 的 JSON 需要
`source`、`source_sha256`、`output`、`base_config`、`patches:[{config: ...}]`、`report`。
每个 patch config 使用既有 pipeline schema，`pilot.start/end` 指向全片绝对时间，
`pilot.output/board` 指向已渲染的窗口和证据。可以 `silent:true`，最终音轨始终从
完整主体复制。patch 必须有序、帧边界对齐且互不重叠，所有渲染指纹须仍有效。
这条路径会重编码画面，不声称未改区域逐像素不变。
