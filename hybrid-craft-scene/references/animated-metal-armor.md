# 有动作的金属圣衣：纹理、反射、曲面各司其职

用户明确要求金属质感时，可以只为装备启用 PBR，保持现有脸、头发和程序动作。
S1E2 R19 的 `directLook()` 把旧 Phong 甲片转成 Toon；新增甲片也是 Toon / Basic。
仅加纹理、提亮颜色或增加自发光不会让高光随视角移动。

## R20 实际接入

共享入口 `dula-assets/characters/stardust/metal-clad.js`：

- `createArmorEnvironment(renderer)` 从定向冷暖反射面生成 PMREM；只给圣衣材质
  显式 `envMap`，不覆盖全场环境或改变已保留的脸部。环境过黑会让全金属甲片发黑，
  应调整反射覆盖与强度，而非恢复大面积自发光。
- `applyMetalClad(actor,{url,environment})` 在 `applyPalaceClad()` 后调用并等待。
  甲面使用真实 metallic/roughness 材质、生成的细刻纹底色与很弱的表面凹凸；
  抛光边条用较低粗糙度。宝石、透明能量缝、披风、伤痕与皮肤不随之金属化。
- 生成图为均匀照明的中性金属刻纹，不画人物、不烤方向性高光。同一细纹可分别
  染铜金与紫钢；身份仍来自盾、肩甲、胸纹和轮廓，不靠贴图区分人物。
- albedo 用 sRGB，bump/data 用 NoColorSpace。底色亮度不是测量的高度：本次只做
  克制的凹凸近似，不能称为生成了真实 PBR 深度或法线重建。
- ExtrudeGeometry 的默认 UV 常接近以米计的小数，需按甲片范围归一化；胸甲环列
  则按圆周与高度布 UV。不要在细小甲面上误用世界地面铺纹方式。
- 稍微弯曲甲面可让反射形成连续变化；面内要有足够细分，并用变换的法线保持连续。
  浮雕、棱线和铆钉须跟同一曲面变形，否则新甲面会埋掉旧细节。本轮实测曾出现
  肩甲三条纹消失，原因正是只弯甲壳、未带动饰件。

`refinePalaceLimbs()` 是另一个可选轮廓适配：只调现有连续腿/臂的粗细分布与护胫
横截面，保留骨长、末端目标及步态。它不是新人体绑定，也不证明自碰撞全部合格。
脸部按用户要求保持；不能在材质任务中顺带重塑已保留的头部。

## 用什么证据判断收益

同一模型、机位、姿态、光照做旧色块/新金属的转面 A/B，检查高光是否移动、
暗部刻纹是否仍可见、边条是否过曝、体积是否变成粗糙岩石。随后看真实格挡、
蹲下、落脚与受击镜头；静态金属球不能替代服装动作样板。

本次为铜金和紫钢两个角色，局部看图与 12 秒 A/B 输出位于
`dula-story/episodes/stardust_clad_s1e2/storyboard/palace_r20/`、
`output/armor_comparison_r20.mp4`。用户尚未对该候选作审美认可。

技术依据：[Three.js PBR 材质](https://threejs.org/docs/pages/MeshStandardMaterial.html)、
[PMREM](https://threejs.org/docs/pages/PMREMGenerator.html)。本次运行版本读取为 0.183.2，
没有为材质试验升级整个依赖链。
