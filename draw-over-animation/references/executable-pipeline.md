# 共享执行工具

这些是实际可执行的跨集工具，不是让新集重新实现的接口愿望清单。
入口 [pipeline.mjs](../scripts/pipeline.mjs)，打包实现 [package_pilot.py](../scripts/package_pilot.py)，
浏览器动作控制模块 [motion-controls.js](../assets/motion-controls.js)。
需要 Node、Puppeteer、Python+numpy、ffmpeg/ffprobe，以及当前 episode 的静态服务。
Puppeteer 从指定 episode 的依赖或上级工作区的 dula-engine 依赖解析。

## 一条入口，五个步骤

```powershell
node <skill>/scripts/pipeline.mjs --episode <episode> --config config/draw_over.json --step prepare
node <skill>/scripts/pipeline.mjs --episode <episode> --config config/draw_over.json --step bake
node <skill>/scripts/pipeline.mjs --episode <episode> --config config/draw_over.json --step render --render
node <skill>/scripts/pipeline.mjs --episode <episode> --config config/draw_over.json --step package
node <skill>/scripts/pipeline.mjs --episode <episode> --config config/draw_over.json --step probe
```

`render` 不带 `--render` 时仅导出配置中的代表帧与构建记录。窗口由试片 `.story`
首尾派生；没有该文件时可显式给 `start/end`，不能以此改写剧情时序。
`prepare` 将 skill 的浏览器模块复制到 episode 指定的生成目录，写来源哈希。
其他步骤也会同步；检测到生成副本被手工改动时停止，先把通用修改合回 skill 正本。
使用 `.js` 是为了兼容既有静态服务的 JavaScript MIME 映射，不用外部绝对路径导入。

## 配置与 episode 适配

以下示例使用通用文件名。`source.sha256` 填已接受原片的真实摘要。路径均相对于
`--episode`，`baseUrl` 是已经启动的服务。共享脚本没有固定集名、人物名、端口、
源时点、画幅或帧率。不同绑定的读取方式写在 episode 适配器中。

```json
{
  "schema": "draw-over-pipeline-v1",
  "baseUrl": "http://127.0.0.1:4250/",
  "source": {"video": "output/accepted.mp4", "sha256": "填原片真实SHA256"},
  "runtime": {"directory": "assets/draw_over_runtime"},
  "pilot": {
    "timeline": "art_pass.story", "fps": 24, "width": 1280, "height": 720,
    "viewer": "art_pass.html?capture=1", "board": "storyboard/art_pass",
    "output": "output/art_pass.mp4", "samples": [], "repeatSamples": [], "hashEvery": 12,
    "sourceFiles": ["art_pass.story", "art_pass.js", "config/draw_over.json", "config/motion.json"],
    "assetDirectories": ["assets/cels"]
  },
  "bake": {
    "viewer": "viewer.html?capture=1", "adapter": "config/capture_adapter.mjs",
    "sourceFiles": ["script.story", "viewer.js", "config/capture_adapter.mjs"],
    "windows": [{"id": "pilot", "timeline": "art_pass.story", "output": "config/motion.json", "consumedByPilot": true}]
  },
  "probe": {"adapter": "config/probe_adapter.mjs", "output": "storyboard/art_pass/motion_check.json"},
  "package": {
    "comparison": "output/art_pass_comparison.mp4", "font": "C:/Windows/Fonts/msyh.ttc",
    "labels": ["原片", "二维作画试片（摄影改动需注明）"],
    "sheets": []
  }
}
```

`samples/repeatSamples` 用源片绝对秒数，必须在窗口内；生产时填代表动作与切镜附近。
帧列 `sheets` 每项为 `{name,start,duration,everyFrames,layout,width}`，`start` 是输出相对秒，
`layout` 如 `4x4`，`width` 默认 384。使用解码帧序号选择而非 fps 重采样，避免把切镜
提前到图上时间标签之前。并排对照会把原片重采样到试片帧率，不改变独立试片。

查看器在初始化完成后提供 `window.ready=true`，提供绝对时间函数
`window.renderAt(t) → {image: PNG的base64, state: 可选诊断数据}`。原 viewer 返回 JPEG 时
需为试片提供 PNG 入口；改扩展名无效。静态服务的启动方式仍沿用各集入口。

烘焙适配器导出 `capture(t, {width,height})`，检查适配器导出 `probe()`；二者在浏览器
页面上下文执行，函数体不能依赖 Node 闭包或模块外局部变量。可以读取页面暴露的
运行态，不能假设不同剧集的骨架和 `__dbg` 名称相同。

`capture` 先更新姿势与最终相机、刷新世界矩阵，再返回：

```js
{
  actors: {
    characterId: {
      root: [x,y,z],
      world: {head: [x,y,z], leftHand: [x,y,z], /* 本镜头控制的其他关节 */},
      projected: {head: [pixelX,pixelY]},
      contact: {left: null, right: null}
    }
  },
  camera: {position: [x,y,z], quaternion: [x,y,z,w], fov: number}
}
```

烘焙自动包含窗口末端边界。`null` 接触不作为通过；源文件摘要失效、非有限坐标、
查看器错误和空素材均显式失败。`probe()` 返回包含 `passed` 的证据对象：选实际发生
运动的帧，检查三维输入和二维修正对像素的作用，再检查固定点、恢复与遮挡等本镜头
关注项。共享执行器保存结果并按 `passed` 退出，不替导演决定审美通过。

## 复用动作控制模块

准备运行模块后，episode 浏览器代码导入其本地生成副本：

```js
import {createMotionController} from './assets/draw_over_runtime/motion-controls.js';
const controls=createMotionController({motion,poseEdits,rigs,pixelsPerMeter:180,maxDelta:38,pinRadius:[90,80]});
controls.update(sourceTime);
const [x,y]=controls.deform(celId,imageX,imageY,authoredDx,authoredDy);
```

- `motion` 是烘焙 JSON；`frameAt(t)` 可读根轨迹等额外数据。
- `rigs[celId]` 为 `{actor,ref,pins,j}`；`ref` 为原画参考帧序号，`pins` 为原画固定点，
  `j[joint]` 为 `[中心x,中心y,影响半径x,影响半径y]`。原画必须人工标定。
- `poseEdits.curves` 为 `{cel,joint,keys:[[frame,dx,dy],...]}`。帧号相对烘焙起点，单位
  是原画像素，区间外修正归零，节点间平滑过渡。
- 三维增量先去根位移，取世界 XY，缩放并限幅，再加二维修正。根位移和镜头由调用方
  处理；若需不同投影轴，先做该镜头的坐标适配，不能声称该算法自动覆盖绕拍。
- `authoredDx/Dy` 可叠加本镜头设计的呼吸、发梢等位移，固定点约束最后应用。

共享模块不包含人物图片、专属火焰、镜头曲线、衣甲造型或自动换脚原画。这些是新集
的内容工作；无需再复制一遍执行器和通用控制算法。

## 已验证范围

首次迁移使用一段 1280×720、30fps、330 帧真实试片：14 个迁移前后代表帧的 PNG
哈希完全一致；28 次反向/重复取帧检查和实际运动输入检查通过。
另用独立临时目录、不同人物键、320×180、12fps、2–2.5 秒窗口的合成夹具运行整条
烘焙→渲染→打包→检查：7 个动作采样、6 个输出帧、5 次确定性检查通过。
这是可移植性验证，不是第二集的艺术验收。

跨帧率夹具曾暴露并排打包继承原片帧率的问题；现明确将两路对齐到试片 fps，并按
输出帧数检查。已有服务也可能不识别 `.mjs` 的 MIME；浏览器模块使用 `.js` 后验证。
完整多角度动画、自动 clean plate、自动骨架识别和走路原画生成均不在已验证能力内。
