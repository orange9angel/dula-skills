# 走路镜头验收：短渲抽帧与 dula-verify 盲区

## 为什么不能只靠 dula-verify

`dula-engine/tools/verify_shots.js:126-161` 按 `script.story` 的 SRT 条目顺序
截图，采样点 = `start + 0.9 × (end - start)`。两个结构性问题：

1. 走路段往往只对应一条脚步声 SFX 条目（甚至没有条目），0.9 采样点经常
   落在走路区间**之外**。cat_leads_e01 的 13 张 check_shot 没有一张落在
   三段走路（10.0–12.5 / 14.0–16.5 / 25.0–27.0）内。
2. 即使落在区间内，一个采样点也看不到 A/B 交替、平移连续性、眨眼跨 cel
   跳变这些**时间维度**的问题。

`validate_walk.py` 会自动做盲区检查：若某段走路区间内没有任何 SRT 采样点，
输出 WARNING。看到这条警告意味着该段只能靠手工短渲验收。

## 短渲 + 抽帧工作流

从 `dula-story` 根目录：

```bash
# 1. 只渲走路区间（例：10–18s 覆盖两段，24–28s 覆盖第三段）
npx dula-render ./episodes/<episode> --start 10 --end 18 --output ./episodes/<episode>/output/walk_10-18.mp4

# 2. 抽帧：起步点、跨 cel 切换点、收尾点各抽
ffmpeg -y -i ./episodes/<episode>/output/walk_10-18.mp4 -ss 0.15 -frames:v 1 /tmp/walk_a1.png
ffmpeg -y -i ./episodes/<episode>/output/walk_10-18.mp4 -ss 0.45 -frames:v 1 /tmp/walk_a2.png
ffmpeg -y -i ./episodes/<episode>/output/walk_10-18.mp4 -ss 0.75 -frames:v 1 /tmp/walk_a3.png
```

抽帧间距对齐 cel 驻留（3.2 cel/s → 0.3125s；2.4 cel/s → 0.4s），保证相邻
抽帧落在不同 cel 上。需要精确对齐时用 `-vf "select=..."` 按帧号抽。

## 逐镜头验收清单

每段走路至少抽 3 帧（起点、一次 A→B 切换两侧、终点前），核对：

- **换腿可读**：相邻抽帧腿部相位明确不同（哪条腿在前、哪只脚跟离地，
  指名核对，不接受"好像在动"）。背影镜头放宽不得——读不出就是 cel
  相位差不够，回 keyframe-walk-shots.md 第 4 条。
- **平移连续**：背景/crop 窗单调滑动，无往返抖动、无逐 cel 重启痕迹
  （抖 = motionGroup 没生效）。
- **人物上半身与构图锁定**：除腿部相位和整体平移外，身体、脸、背景元素
  位置不跳（跳 = cel 不同构图或尺寸不一致）。
- **无矩形闪**：A/B 切换时没有局部色块闪动（有 = B 帧是羽化贴回，须全幅
  重生成）。
- **无平色区背景互闪**：切换点前后两帧平移对齐后 diff，小腿/脚部周围的
  平色背景（路面、光斑）不应有成片实块差异——人眼盯着脚，紧邻的背景
  重画最刺眼（cat_leads frame_06 v6 对教训，2026-08-15）。有 = 两张 cel
  各自整图重生成且背景没锁住；锁不住就按 keyframe-walk-shots.md「选型」
  节改静帧/近远两拍方案，不要用遮罩合成补救（接缝只会转移）。
- **眨眼连续**：带 eyeRig 的段，眨眼只按 rig 时钟发生，换 cel 瞬间眼睛
  状态不跳变（跳 = blinkCarry 缺失/错位）。
- **程序化层不穿脸**：cloudDrift/steam/dappleSway 的源图坐标不压角色面部
  （cat_leads V2 教训：漂移云压脸像"气泡"）。

## 抖动排查方法论（v10–v11 实测沉淀）

观众报"抖动"时按层排查，每层都有量化手段，不要直接改图：

1. **源图层**：cel 两两 PIL diff——框外区域应为 0.00%；若编辑矩形里的
   路面/纹理被重新生成，切换时矩形框会跳（V5 矩形闪的现代版）。
2. **原始渲染帧**：`storyboard/frames/` 保留了未压缩 PNG。逐帧 diff
   驻留期应只有平移/程序化层的平滑变化（~2–4%），切换帧才应跳变。
3. **编码层**：从 mp4 抽帧对比原始帧时**必须按帧号对齐**
   （`-vf "select=eq(n,N)"`），`-ss` 秒数抽帧会和 `frame_%05d` 编号差一帧，
   平移+换腿的素材会量出假的"编码误差集中区"（实测踩过：误判 x264
   宏块泵浦，按帧号对齐后误差均匀）。
4. **支撑脚一致性**：contact↔passing 的循环量脚部接触带分区 diff——
   摆动脚区变化大是正常的，支撑脚区 >3% 就是落点瞬移（"小腿周围矩形
   区域抖动"的真凶）。

## 入库前的结构验证

```bash
python ../dula-skills/walk-director/scripts/validate_walk.py ./episodes/<episode>
python ../dula-skills/walk-director/scripts/validate_walk.py ./episodes/<episode> --strict   # warning 也算失败
```

结构验证通过只是入场券；以上抽帧清单全过才算走路镜头验收完成。
