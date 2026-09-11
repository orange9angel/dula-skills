---
name: map-transition-ad
description: Make a Douyin "3D map transition" creative ad (陶阿狗君 style): a mascot/animal character tours N cities inside a map-app UI — pin drop hook, zoom-blur into the map, per-city costume gags, beat-snapped swipe transitions, optional audio-driven talking, freeze+shutter ending. Use when you have a character idea and want a 10-20s vertical (9:16) creative ad without any GUI editor.
---

# Map Transition Ad（地图转场创意广告）

对标抖音"3D地图转场/旅行打卡"类创意广告（陶阿狗君式：技术流+幽默+
意想不到的转场）。角色（动物/吉祥物，**无人脸墙**）在地图 App 里巡城变装。

参考实现（已出片验证 2026-09-12）：`dula-story/episodes/croc_map_ad/`
（鳄鱼 demo 11.5s，≈¥9）。工具脚本都在该 episode 的 `tools/` 下，幂等可复跑。

## 管线

1. **定帧**（codex imagegen 免费，或 seedream ¥0.3/张）：先出**角色定稿**
  （直立、全身、身份锚点清晰——鳄鱼案例：墨镜+金链），再图生图衍生
  每城一张"巨人在微缩城市"定帧（9:16）。**身份锚点每张必带**，只改
  服装/场景。
2. **台词**（可选）：seed-tts 逐句生成（`seedtts_say.py`），每城一句
  gag 台词，方言梗最佳。
3. **视频段**：微动段 = Seedance I2V 首帧（¥4/4s）；**说话段 = Seedance
  2.0 图+音频组合参考**（同价，E09-W2 已验证，见
  build-continuous-story-images/references/live-action.md 通道地图）。
4. **后期合成**（PIL+numpy+ffmpeg，零 GUI，参考 `tools/build_demo.py`）：
  - **地图 UI 一律后期画**（搜索栏/底部城市卡片/POI 标注/导航圆钮）——
    生成模型画 UI 文字必糊，这条是铁律。
  - 图钉落下钩子：2D 贴图 + ease-out 二次弹跳，落点吸附 BGM 拍点。
  - 进城：zoom-blur（前段加速推镜模糊 ↔ 后段拉出清晰）。
  - 换城：swipe——双画布横移 + smoothstep + 中段方向性动态模糊，
    底部卡片同步滑动换城市名。
  - 卡点：beatcut-edit 的 onset 检测，事件吸附到每 8 拍一组的网格。
  - 收尾：定格 1s 缓推 + 0.1s 闪白 + 程序合成快门声（promo-cut 配方）。
  - 混音：BGM 归一 0.85，说话段压 0.25 不消失，叠完二次限幅 0.95。

## 翻车记录（croc demo 实测）

- **台词被定格切掉**：freeze 必须排在"说话有效内容结束"之后的下一拍
  （silencedetect 先量有效语音长度，别信文件时长——尾静音不算）。
- **图钉挡脸**：角色顶到画面顶时图钉没地方落——intro 段用 zoom-out
  （下条）把角色缩小到 ~85%，头顶留出图钉位。
- **zoom-out 缩图出接缝**：直接 paste 到纯色底会有矩形边；改用**边缘像素
  复制**扩画幅（np.pad edge），纯色/渐变背景无缝。
- **贴图糊脸**：贴图类元素（图钉/卡片）缩放用 LANCZOS，锚点位置按
  缩放后的角色头部坐标重算，别复用原图坐标。

## 成本基线

| 项 | 价 |
|---|---|
| 定帧（codex imagegen） | ¥0（seedream ¥0.3/张） |
| I2V 微动 / 音频驱动说话段 | ¥4.02/4s @720p（一样价） |
| TTS | <¥1/句 |
| 后期 | ¥0 |

12s/2 城 demo ≈¥9；15s/4 城全量版 ≈¥35–50。

## 验收纪律

- 抽帧目检：图钉落点不挡脸、UI 文字无乱码、swipe 中段无撕裂、
  说话段口型开合与语音窗口对齐（silencedetect 量）、定格无黑帧。
- 听感：语音不被 BGM 淹（说话时 BGM≤0.3）、快门声落在定格起点、
  无削波。
