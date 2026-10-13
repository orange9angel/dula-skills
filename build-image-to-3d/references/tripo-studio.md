# Tripo Studio 浏览器适配

用于自己的 Tripo Studio 账号做图生角色试验。Studio 网页点数与开发者 API 点数是
不同体系；网站试用余额不能直接当 API 余额。先读当前浏览器技能 `kimi-webbridge`。

## 当前可用范围

2026-10-14 已实测：复用已登录 Chrome 后台标签、上传参考图、H3.1 图生带纹理模型、
记录回执与点数变化、减面、Mixamo 自动绑定、预设 walk 与正常 GLB 导出。免费阶段
H3.1 导出触发会员提示；用户自行购买 Pro 后导出成功。男女主已拿到带 walk 的 GLB。
本地 Three.js 已播放动画并用 IK 控制抬手和转头；这不等于面部或整集表演验收。

独立 Playwright 无头 profile 经自然等待后仍停在网站安全验证页；因此无头访问目前
标记为 **未通过**，不能把后台标签操作称为 headless。沿用可用的真实登录浏览器；
不要绕过验证码或因探测失败反复重提收费任务。

## 单次任务操作

1. 从用户要求提取角色数与点数上限；已有授权内不重复询问。查看登录状态、余额、
   生成按钮的费用、当前模型版本和导出权益。先用单个代表角色；不自动购买会员。
2. 用完整全身中性 A/T 姿参考图。手臂离开躯干、双腿分开、手指可辨；背面是生成推断。
   保存图、完整 prompt、哈希和来源。普通文生图参考不算三维生成结果。
3. 同一任务使用同一个 Kimi session。点击前启动网络记录。Windows 命令体使用 UTF-8
   临时 JSON 文件，调用后删除。优先快照找控件；下拉菜单若 `.click()` 不生效，按
   当前 DOM 边界使用 CDP 原生输入，不猜页面固定坐标。
4. 上传先用 `upload`；若扩展没有文件 URL 权限，可由宿主读取**用户授权的具体图片**，
   将字节传入网页内存构造 `File`/`DataTransfer` 并向图片 input 派发 change。这样不读取
   浏览器本地文件或更改扩展权限。不要把 Cookie、密码、浏览器数据库混进上传流程。
   已将实际上传方法收敛到 `scripts/tripo_upload_reference.py image.png --session <当前任务>`；
   只上传、不生成，检查当前域名、图片格式和 20 MB 上限。沿用任务 session，不另开标签。
5. 提交一次后检查余额变化与网络回执。2026-10 页面生成端点为
   `/v2/studio/operation/image_to_model`，成功体含 `project_id` 和 `operator_id`。
   这只是已观察到的网页协议，不承诺稳定 API；不硬编码服务端扣费规则。
6. 保存回执里的任务 ID、所选参数、输入位置与余额变化，过滤鉴权请求头和签名 URL。
   URL/页面变化具有异步延迟；按钮返回成功或旧快照不证明提交成功或失败。
   超时先按任务 ID 查现有任务，绝不直接再次点击 Generate。
7. 生成结束看正/侧/背；检查手指、衣袖、马尾和裙摆，随后才做必要的减面、自动绑定
   和动画预览。每一步重新核对费用，累计不超过已授权预算。
8. 导出按正常 Export 对话框。出现 Upgrade 时记录限制，不从预览网络链接提取 GLB
   绕过导出权益。可在授权预算内另测免费可导出的版本，但要明确这是新的生成结果。
9. 数值输入显示更新不代表应用状态已提交。一次减面框显示 20000，但回执仍为 10000。
   使用控件支持的原生键盘/滑块提交并检查回执；输出清点以实际面数为准，不能事后改写参数。
10. Export 的 Number of Animations 默认 0，选择 walk 后须勾选要导出的动画。正常下载
    目录由 Chrome 配置决定，并非总在用户 Downloads。导出窗口不自动关闭不代表失败。
    先查文件存在、大小、哈希和动画内容，别重复提交生成。

## 本地导入的实际缺陷

- 一份 skeleton-only GLB 虽有 55 joints，但 24733/24736 个顶点仅跟随 Hips，且 joint
  节点为 identity。`skeleton.pose()` 能从 inverse bind 恢复姿态，却不能修复错误权重。
  同项目带 walk 的导出有 65 joints、分布合理的手脚权重，可克隆后 pose() 作为控制底座。
  这是有文件证据的个例，不笼统断言所有 Tripo 绑定均损坏。须解码 JOINTS/WEIGHTS 并做动作测试。
- 两份导出的姿态不同不代表单位不同。用同一绑定姿态的尺寸归一化，不能分别按动画帧
  的屈膝高度缩放，否则走路突然放大、脚被裁掉。root motion 单独决定保留还是原地播放。
- 共用 twoBone 的 pole 是弯曲方向向量，不是世界位置；误加肩点会让肘部向上翻。
- 4K 全身颜色贴图不等于面部有 4K 像素，也不等于最终视频 4K。模糊/块状感先区分
  参考图、生成纹理、UV 分配、几何减面、顶点法线/切线、光照和编码，不能直接推销 8K。
  此次颜色图实际 4096²，法线图 2048²，导出没有 TANGENT；关闭法线或计算 MikkTSpace
  切线后，近景三角明暗块明显减少。没有证据时不把粗糙全部归因于贴图分辨率或会员档位。
  保留同镜头原始/候选 A/B；禁用法线只能是诊断或经审查的取舍，不能声称恢复了丢失细节。
- 单体衣裙可能被错误赋予手臂权重，抬手时裙边跟手走。身体骨架能动不代表衣物变形合格。
  动态检查至少包含抬手与走路；手指、衣摆、眼神和口型分别验收。

原始高模可从画布的 History 图标（实测 `i-tripo:time-past`，未必是 button）选择旧版本。
只预览/导出时不要按 Restore 覆盖当前工作版本。所有历史资源依旧通过正常 Export 获取。

### 已验证的局部替代路线

同一 Aoi 原始约 197 万面高模在相同 720p 近景下明显比 1.93 万面重拓扑版平顺，
说明不能仅调整视频分辨率或关闭法线就宣布修好。保留原高模 UV 与 4K 原纹理，
用本地 Blender Collapse 减至 16 万面，再从已审计的 walk 导出转移蒙皮权重；
近景与本地走路/抬手已看到明显改善。脸部控制、衣裙权重及整集接入仍须另外验证。

`scripts/prepare_rigged_lod_blender.py` 接收 `--high/--rig/--out/--triangles`，只写候选文件，
检查两份资产绑定空间包围盒接近，最近表面插值转移权重，限 4 个影响并归一化，
输出过程记录与哈希。本次 Aoi 约 33 秒；不是跨机器性能承诺。使用：

```powershell
blender -b --python-exit-code 1 --python prepare_rigged_lod_blender.py -- --high original.glb --rig walk.glb --out candidate.glb --triangles 160000
```

- `--python-exit-code 1` 必须保留，否则 Blender 脚本异常可能仍返回进程 0。
- 导入器会创建 Icosphere 骨骼显示辅助物；用 Armature modifier 识别蒙皮网格，不能
  假设所有导入 MESH 都是角色网格。
- 权重转移要在 REST pose 下做；保留原始文件，导出后重新检查动画和真实关节形变。
- 这不是凭更多面数自动达标；新 UV 烘焙、低面数模型和导入材质须拆开对比。

## 费用与能力不要混为一谈

实际例：H3.1 带 PBR 纹理、detailed geometry/texture，页面 55 点，余额 200→145。
输出约 197 万三角面；Auto Rig 显示 20 点，但先报 Polygon Limit Exceeded，**此时未扣
绑定费用**。页面转至 20,000 面 Smart Mesh P1.0 重拓扑，按钮显示 35 点。
这些数值仅为有日期的实测，下一次以当前界面为准。

免费计划的公开性、商用限制、导出版本限制分别核对
[官方价格页](https://www.tripo3d.ai/pricing)。生成点数足够不代表可以下载、商用或完成
面部动画。会员也不保证肩肘、衣摆、手指权重正确。

## 无头探测

`scripts/tripo_studio.py probe` 使用独立持久 profile，默认 headless，只读取页面。
profile 默认位于忽略的 `dula-story/.tripo_profile/`。探测输出不包含输入值、Token、
Cookie 或 storage；只记录可见文字与状态。支持 `--url` 查询已有项目页面。

```powershell
dula-story/.venv/Scripts/python.exe dula-skills/build-image-to-3d/scripts/tripo_studio.py probe
```

`login` 入口仍属未验证路径，仅从 `TRIPO_EMAIL` / `TRIPO_PASSWORD` 读取凭据；遇到站点
验证即报告 `site_verification_required`。不要通过命令参数传密码，不把未验证的登录
选择器称为稳定自动登录；需要用户接管时说明真实原因。
