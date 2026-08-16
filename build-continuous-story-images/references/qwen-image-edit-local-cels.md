# qwen-image-edit：本体保持的局部 cel 编辑（眨眼/口型/互动中间画）

> 来源：xiaoju_secret 生产周期（2026-08-16）。当 codex imagegen 配额不可用或
> 需要按量付费的替代方案时，这是角色 cel 编辑的首选通路。

## 模型选择（百炼图像模型分工）

| 模型 | 适用 | 不适用 |
|------|------|--------|
| `qwen-image-edit` | **角色 cel 局部编辑**（眨眼/口型/表情/小动作），本体保持强 | 需要像素级掩码约束的极小编辑（它不听掩码，听构图锁定提示词） |
| `wanx2.1-imageedit`（description_edit_with_mask） | 风格化重绘、允许"重新理解"的编辑 | **角色 cel**——掩码内重画会漂移本体（花纹/脸型被重画成另一个角色），生产事故见下 |
| `wan2.7-image-pro` 等文生图 | 关键帧/母版全绘 | 局部编辑 |
| codex imagegen | 订阅额度内的同等级 cel 编辑 | 配额锁定时不可用 |

**生产事故记录（wanx 用于角色 cel）**：蹭手中间画的掩码罩住整个猫头，猫的条纹/脸型被
重画成另一只猫（用户原话「猫都变成另外一只了」）；同一图像多处眨眼 cel 眼睑质感不一。
换 qwen-image-edit 后全部解决。**角色一致性编辑一律走 qwen-image-edit。**

## 调用形态

```python
from dashscope import MultiModalConversation
rsp = MultiModalConversation.call(
    model="qwen-image-edit",
    messages=[{"role": "user", "content": [
        {"image": f"data:image/png;base64,{b64}"},   # base64 data URL 直传
        {"text": prompt}]}])
url = rsp.output.choices[0].message.content[0]["image"]  # 签名临时 URL，立即下载，不要存 URL
```

注意：输出尺寸由模型决定（1672×941 输入 → 1376×768 输出），用回贴前 resize 回原尺寸。

## 构图锁定提示词模式

qwen-image-edit 没有掩码参数，靠提示词锁定：

```
保持画面构图、人物/动物的位置和大小完全不变。只把<目标特征>改成<目标状态>。
<角色>的花纹、毛色、脸型/发型、肤色必须和原图完全一致，其余内容保持不变。
```

- 眨眼必须明说「两只眼睛都闭合」并加「禁止单眼睁开」级别的约束仍可能出 wink——验收时逐眼检查。
- 闭眼类编辑建议加「眼睑合上、覆盖毛发/皮肤、带睫毛」的正面描述，比「闭眼」二字稳定。
- wanx 掩码编辑的对应要求：必须明说「眼球消失」，否则模型倾向保留睁眼。

## 完整 cel 工作流（blink/mouth/interaction 通用）

1. **特征定位**：在源图用 NEAREST 放大 + 网格叠加图读坐标，或行扫描打印像素值、
   颜色连通域检测（如猫眼绿）取中心。**禁止凭缩略图目估**——目估误差可达 ±80px，
   是 cel 错位的头号根因。
2. **裁剪编辑**：裁特征区（带足够上下文），构图锁定提示词送 qwen-image-edit。
   （wanx 通路则要求图高 ≥512px，裁剪图先放大。）
3. **贴回**：只把特征椭圆区域羽化贴回基帧（feather 4–8px）。贴回区外必须恢复基帧
   像素——整张贴回会把重绘噪声带进 cel，12fps 切换时整个矩形闪烁（V1.1 事故）。
4. **diff 验证**：贴回后与基帧 diff，确认变化 confined 在特征区且确实发生。
5. **rig 装配**：rect 取变体与基帧 diff 的 union bbox + pad，由脚本生成
   mouth_rigs.json / eye_rigs.json，不要手写。
6. **成片定刻抽帧**：cel 验收必须在渲染成片的调度时刻抽帧确认，只看变体图会漏掉
   rect 级错位（wink、错位 20px 都漏过）。

## 互动中间画（蹭手/拥抱等）

整图送 qwen-image-edit + 构图锁定，作为独立镜头帧插入时间线（0.8–1.2s beat）。
注意场景引擎的运镜 progress 按时间线条目重置：alt 条目沿用同一 move 会有 ~1% 的
zoom 回跳（切镜可掩盖），不要给 alt 条目换不同 move。掩码/构图重画若改变主体位置
过大（如转头换成正脸），会读作跳帧而非互动——弃用，不要硬用。

## 废案回收

整图重渲染的"废案"里常有局部优质内容（如整张漂移但闭眼画得好）。用 diff 定位内容
位置，缩放对齐后羽化贴回基帧特征区即可变废为宝（frame_09 猫眨眼即此救回）。

## 成本参考（2026-08 用户账户实测）

- CosyVoice v3 flash 配音：当前免费
- qwen-image-edit / wanx 图像编辑：按量计费，几分钱/张量级
- 百炼控制台：https://bailian.console.aliyun.com/
