# 2D 关键帧序列场景（*SequenceScene.js）的程序化层纪律

适用对象：cat_leads_e01_sunny_store / rainy_rooftop_cat / snow_fox_shrine 一类
"整图 PNG + crop 运镜 + 源图空间程序化层"的 2D 管线场景（非 3D 场景）。

## 坐标必须实测，不目测（2026-08-15 snow_fox_shrine 教训）

程序化层的所有源图坐标（emitter、glow、spot、rect）一律从**源图实测**，
不要从整图目测估计：

- 目测的 lanternFlicker 光斑漂到天空/雪地上，低 alpha 琥珀叠深靛渲染成
  泥巴色污块（首渲验收才发现）。
- 实测方法：角色面部/嘴位用变体 diff bbox（`auto_lock_variants.py` 的
  输出 rect 就是现成测量）；静物（灯笼窗、道具）用 ReadMediaFile 的
  region 裁剪逐张量。
- 交付前必查：短渲抽帧时专门看一眼每个程序化层的落点，叠错位置的层
  比没有层更糟。

## 层纪律（沿用各集 STYLE_BIBLE 共识）

- 一切程序化层画成**源图空间**的硬边平涂形状：零模糊、零渐变、零噪点，
  柔感只用 alpha 表达；crop 运镜会带着层一起走。
- 层是时间的确定性纯函数（hash 播种），保证重渲/交叉淡化可复现。
- 宁可少叠：每层都要有明确的叙事/空间动机（落雪=天气、呼气=寒冷、
  蒸汽=热食、灯笼呼吸=光源活性），无动机的层不加。
