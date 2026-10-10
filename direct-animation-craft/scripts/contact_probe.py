"""contact_probe.py — 配置驱动的接触/物理探针（direct-animation-craft skill 通用版）。

吃一份 render trace（viewer 侧探针输出契约见 references/physics-gate.md：
每帧 state.contact / state.doorway / state.<whitelist_section> / state.env 等键）
+ episode 侧 contact_contract.json，输出与 trace 同目录的 contact_validation.json。

断言库（contract 里逐段参数化；缺帧/缺主体/缺障碍物即失败）：
  doorway        门/交互物网格段：窗口覆盖完整性、采样率、单调、障碍物与主体覆盖、零命中
  whitelist      声明式接触清单：托盘/抓握等合法接触按 主体×部件×障碍×窗口 放行，其余即失败
  env            环境净空段：任何命中即失败
  seated         手-躯干轴 XZ 距离窗口（不插进躯干、不悬浮）
  bite           窗口内最小距离断言（如签尖到嘴至少一次 <阈值）
  carry          端持窗口最近手-物贴合（XZ 与 dy 双阈值）
  food           食物握持：尖-球心上限 + 指骨-球心下限
  wrist          手腕生理域：扭转实加上限 + 掌⊥前臂（|dot| 上限）
  tray           托盘一致性：约束强度>k_min ⇒ 掌-盒距离 < 该托持偏移+余量
  supporter      支撑者存在性：可见且非静置/过渡段 ⇒ 手或下层盒在支撑距离内
  lid            盖随手动：盖角速度非零 ⇒ 主人的手在盖把 max_dist 内
  pinch          捏持锚点：点-线距离窗口域（不戳掌心不脱手）
  dual           双手搬运：窗口内每只手都在盒旁
  place          放置段手-盒距离窗口（分段阈值：引导段/落台推滑段）
  continuity     放置连续性（按姿势帧率比较）+ 放手后静置（逐输出帧）
  gait           步态域：walk 帧速度上限 / bout 均速下限 / bob 振幅下限 / 步频域（按角色分参数；
                 需要 trace 的 state.locomotion[actor]={kind,root,step,bob}）
  limb_attach    肩臂衔接：上臂轴（肩→肘）与躯干垂线夹角上限（抬臂过肩线=袖根脱嵌风险）
                 + 肩点到躯干轴线距离上限；需要 state.contact.arms / torsoAxis
  worn_prop      穿戴件净空：state.worn（穿戴者网格 vs 穿戴件盒，负 margin=深穿才报）零命中
  grip           托盘接触成立：掌面-盒底缝 ≤palm_max 且掌在盒底投影内（contact.grip[key].palmGap/
                 inFoot）+ 扣边成立（至少一指节距盒体 ≤finger_max，contact.grip[key].fingerMin）
  palm_semantic  动作语义掌向：bring-to-mouth 类帧掌心-躯干点积 ≥min_dot（掌心朝向躯干半球；
                 viewer 只在约束激活帧记录 contact.palmIn[key]）
  hand_body_mesh 手-躯干/大腿网格级相交：state.handBody（手 skinned mesh vs 代理盒，负 margin
                 深穿才报）窗口内零命中，allowed 行按 手×代理×窗口 声明合法接触
  rest_support   静息手必有支撑：坐姿窗口内手速 <max_speed 且手高 <max_y 时，
                 contact.handRest[actor][side].support（贴腿/贴盒取小）≤gap_max
  state_consistency 状态一致性（finalize 段做全时间轴分析）：有状态元素（门/盒盖）的
                 迁移窗口 from/to 态成立 + 触发者在场（角色距离/手近盖把/环境阵风量）+
                 音效事件落在迁移窗口 ±tol + 行为-状态规则（角色过门平面帧门必须开）

Usage:
  python contact_probe.py <trace.json> --contract <episode>/config/contact_contract.json [--door-only]
"""
import argparse
import json
import math
from pathlib import Path

DEFAULT_SCOPE = ('Visible solid meshes vs rendered obstacle boxes, triangle intersections; '
                 'sampled collision audit, not continuous physics or artistic approval.')

# 段执行顺序固定（报告 failures 的帧内段序与既有 episode 实现对齐用）；
# 新段只准追加在末尾，插入中间会改变 failures 帧内序、破坏跨版本报告可比性
SECTION_ORDER = ['seated', 'bite', 'carry', 'whitelist', 'env', 'food', 'wrist', 'tray',
                 'supporter', 'lid', 'pinch', 'dual', 'place', 'continuity',
                 'gait', 'limb_attach', 'worn_prop', 'grip', 'palm_semantic',
                 'hand_body_mesh', 'rest_support', 'state_consistency']


def dist(a, b):
    return math.dist(a, b)


def state_consistency_pass(SC, data, stats, failures):
    """状态一致性（全时间轴分析）：迁移 from/to 态成立 + 触发者在场 + 事件对齐 + 行为符合状态。"""
    frames = data['frames']

    def cval(f, path):  # contact 键路径 'a.b'，值可以是数值或数组
        v = f.get('contact') or {}
        for k in path.split('.'):
            v = v.get(k) if isinstance(v, dict) else None
        return v

    for ename, E in SC['elements'].items():
        vals = [(f['t'], cval(f, E['key'])) for f in frames]
        vals = [(t, v) for t, v in vals if isinstance(v, (int, float))]
        if not vals:
            failures.append(f"state element series missing: {ename} ({E['key']})")
            continue

        def vat(tt):
            return min(vals, key=lambda x: abs(x[0] - tt))[1]

        open_min, closed_max = E['open_min'], E['closed_max']
        for tr in E.get('transitions', []):
            tid = f"{ename}.{tr['id']}"
            w0, w1 = tr['window']
            v0, v1 = vat(w0 - .03), vat(w1 + .03)
            if tr['from'] == 'closed' and v0 > closed_max:
                failures.append(f"{tid}: not closed before window (open frac {v0:.2f})")
            if tr['from'] == 'open' and v0 < open_min:
                failures.append(f"{tid}: not open before window (open frac {v0:.2f})")
            if tr['to'] == 'closed' and v1 > closed_max:
                failures.append(f"{tid}: not closed after window (open frac {v1:.2f})")
            if tr['to'] == 'open' and v1 < open_min:
                failures.append(f"{tid}: not open after window (open frac {v1:.2f})")
            ev = tr.get('event')
            if ev:
                stats[f'state_{tid}_event_offset'] = round(max(w0 - ev['t'], ev['t'] - w1, 0), 3)
                if not (w0 - ev['tol'] <= ev['t'] <= w1 + ev['tol']):
                    failures.append(f"{tid}: event @{ev['t']} outside transition window±{ev['tol']}")
            tg = tr.get('trigger') or {}
            if 'actor' in tg:  # 触发者角色在元素交互距离内（root XZ → 元素 pos XZ）
                dmin = 99
                for f in frames:
                    if not (tg['window'][0] <= f['t'] <= tg['window'][1]):
                        continue
                    p, r = cval(f, E.get('pos_key', '')), f.get(tg['actor'] + 'Root')
                    if isinstance(p, list) and isinstance(r, list):
                        dmin = min(dmin, math.hypot(r[0] - p[0], r[1] - p[2]))
                stats[f'state_{tid}_trigger_dist'] = round(dmin, 3)
                if dmin > tg['max_dist']:
                    failures.append(f"{tid}: trigger {tg['actor']} never within "
                                    f"{tg['max_dist']}m of {ename} (min {dmin:.2f}m)")
            if 'gust_key' in tg:  # 环境触发：窗口内阵风量达标（画面中可见的动因）
                gmax = max((cval(f, tg['gust_key']) for f in frames
                            if tg['window'][0] <= f['t'] <= tg['window'][1]
                            and isinstance(cval(f, tg['gust_key']), (int, float))), default=0)
                stats[f'state_{tid}_gust_max'] = round(gmax, 3)
                if gmax < tg['min']:
                    failures.append(f"{tid}: no gust (max {gmax:.2f}) in trigger window")
            if 'hand_near' in tg:  # 手在盖把/交互点距离内
                key = 'lidTabDist.' + tg['hand_near']['tab_key']
                dmin = min((cval(f, key) for f in frames
                            if tg['window'][0] <= f['t'] <= tg['window'][1]
                            and isinstance(cval(f, key), (int, float))), default=99)
                stats[f'state_{tid}_hand_dist'] = round(dmin, 3)
                if dmin > tg['hand_near']['max_dist']:
                    failures.append(f"{tid}: no hand near {tg['hand_near']['tab_key']} "
                                    f"(min {dmin:.2f}m)")
        # 行为-状态规则：角色穿过门平面的帧，门必须开（穿越=法向投影变号且在门宽内）
        B = (E.get('behavior') or {}).get('cross_plane')
        if B:
            pt, nm, hw = B['point'], B['normal'], B.get('half_width', .6)
            for actor in B['actors']:
                roots = [(f['t'], f.get(actor + 'Root')) for f in frames]
                roots = [(t, r) for t, r in roots if isinstance(r, list)]
                for (t0, r0), (t1, r1) in zip(roots, roots[1:]):
                    d0 = (r0[0] - pt[0]) * nm[0] + (r0[1] - pt[1]) * nm[1]
                    d1 = (r1[0] - pt[0]) * nm[0] + (r1[1] - pt[1]) * nm[1]
                    if d0 * d1 < 0 and abs(r0[0] - pt[0]) <= hw:
                        v = vat((t0 + t1) / 2)
                        stats[f'state_{ename}_cross_{actor}'] = round(v, 3)
                        if v < B['open_min']:
                            failures.append(f"{ename}: {actor} crosses plane with door closed "
                                            f"(open frac {v:.2f}) @t={t0:.2f}")


def torso_dist(hand, root):
    return math.hypot(hand[0] - root[0], hand[2] - root[1])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('trace', type=Path)
    ap.add_argument('--contract', type=Path, required=True)
    ap.add_argument('--door-only', action='store_true')
    args = ap.parse_args()
    C = json.loads(args.contract.read_text(encoding='utf-8'))
    data = json.loads(args.trace.read_text())
    tick_hz = C.get('pose_tick_hz', 15)
    failures = []

    # ── doorway：交互物网格段 ──
    stats = {}
    if C.get('doorway'):
        D = C['doorway']
        w0, w1 = D['window']
        fps = data.get('fps', 0)
        door_frames = [f for f in data['frames'] if w0 <= f['t'] < w1]
        stats.update({'door_frames': len(door_frames), 'door_collision_frames': 0,
                      'bite_min': 99., 'carry_max_xz': 0., 'seated_min': 99., 'seated_max': 0.})
        if fps < C.get('fps_min', 30):
            failures.append('door coverage: sampling must be at least 30Hz')
        step = 1 / max(1, fps)
        if not door_frames or door_frames[0]['t'] > w0 + .001 or door_frames[-1]['t'] < w1 - step - .001:
            failures.append(f'door coverage: require the complete {w0}–{w1}s window')
        if any(b['t'] - a['t'] > step + .001 or b['t'] <= a['t'] for a, b in zip(door_frames, door_frames[1:])):
            failures.append('door coverage: missing or nonmonotonic samples')
        required = set(D['required_obstacles'])
        skinned_min = D.get('skinned_min', {})
        for frame in door_frames:
            t = frame['t']
            probe = frame.get(D.get('state_key', 'doorway'))
            if not probe:
                failures.append(f'door probe missing @t={t}')
                continue
            if not required.issubset(probe['obstacles']) or probe['margin'] < D['margin_min']:
                failures.append(f'door obstacle coverage/margin incomplete @t={t}')
            for sub in D['subjects']:
                if t >= sub['start'] and not probe['counts'].get(sub['name']):
                    failures.append(f"door subject missing: {sub['name']} @t={t}")
                if t >= sub['start'] and skinned_min.get(sub['name']) and \
                        probe.get('skinnedCounts', {}).get(sub['name'], 0) < skinned_min[sub['name']]:
                    failures.append(f"door skinned-hand coverage missing: {sub['name']} @t={t}")
            if probe['hits']:
                stats['door_collision_frames'] += 1
                failures.append(f"door collision @t={t}: {probe['hits'][:3]}")
    else:
        stats.update({'bite_min': 99., 'carry_max_xz': 0., 'seated_min': 99., 'seated_max': 0.})

    prev_box = {}  # continuity / lid 段的上一帧状态
    gait_prev, gait_bout, gait_bouts = {}, {}, {}  # gait 段：帧间根位/步序、当前 bout、已闭合 bout
    rest_prev = {}  # rest_support 段：各手位置历史（~0.1s 窗算手速，防 15Hz 姿势帧间冻结误判静息）
    whitelist_allowed = (C.get('whitelist') or {}).get('allowed', [])

    def hit_allowed(hit, t):
        for row in whitelist_allowed:
            if row['subject'] != hit['subject']:
                continue
            parts = row.get('parts') or [row.get('part')]
            if hit['mesh'] not in parts:
                continue
            if row.get('obstacle_prefix'):
                if not hit['obstacle'].startswith(row['obstacle']):
                    continue
            elif hit['obstacle'] != row['obstacle']:
                continue
            w = row['window']
            if w[0] <= t <= w[1]:
                return True
        return False

    for frame in data['frames']:
        if args.door_only:
            break
        t = frame['t']
        c = frame.get('contact')
        if not c:
            continue
        for section in SECTION_ORDER:
            S = C.get(section)
            if not S:
                continue
            if section == 'seated':
                if S['window'][0] <= t <= S['window'][1]:
                    for actor, root_key in S['actors'].items():
                        root = frame.get(root_key)
                        if not root:
                            continue
                        for hand in c['hands'][actor].values():
                            d = torso_dist(hand, root)
                            stats['seated_min'] = min(stats['seated_min'], d)
                            stats['seated_max'] = max(stats['seated_max'], d)
                            if d < S['min']:
                                failures.append(f"hand in torso: {actor} {d:.3f}m @t={t:.2f}")
                            if d > S['max']:
                                failures.append(f"hand floating: {actor} {d:.3f}m @t={t:.2f}")
            elif section == 'bite':
                if S['window'][0] <= t <= S['window'][1] and c.get(S['a']):
                    d = dist(c[S['a']], c[S['b']])
                    stats['bite_min'] = min(stats['bite_min'], d)
            elif section == 'carry':
                for e in S['entries']:
                    box = c.get(e['box'])
                    if not box or not (e['window'][0] <= t <= e['window'][1]):
                        continue
                    xz_max = e.get('xz_max', S['xz_max'])
                    dy_max = e.get('dy_max', S['dy_max'])
                    best = min(math.hypot(hand[0] - box[0], hand[2] - box[2])
                               for hand in c['hands'][e['actor']].values())
                    stats['carry_max_xz'] = max(stats['carry_max_xz'], best)
                    hand = min(c['hands'][e['actor']].values(),
                               key=lambda h: math.hypot(h[0] - box[0], h[2] - box[2]))
                    dy = hand[1] - box[1]
                    if best > xz_max or dy > dy_max or dy < -dy_max:
                        failures.append(f"carry off-box: {e['actor']} xz={best:.3f} dy={dy:.3f} @t={t:.2f}")
            elif section == 'whitelist':
                b = frame.get(S.get('state_key', 'bento'))
                if not b:
                    continue
                stats.setdefault('bento_frames', 0)
                stats['bento_frames'] += 1
                stats.setdefault('bento_tray_contacts', 0)
                for hit in b['hits']:
                    if hit_allowed(hit, t):
                        stats['bento_tray_contacts'] += 1
                    else:
                        stats['bento_bad'] = stats.get('bento_bad', 0) + 1
                        failures.append(f"bento clip @t={t}: {hit['subject']} {hit['mesh']} vs {hit['obstacle']}")
            elif section == 'env':
                env = frame.get(S.get('state_key', 'env'))
                if env:
                    stats['env_frames'] = stats.get('env_frames', 0) + 1
                    for hit in env['hits']:
                        stats['env_bad'] = stats.get('env_bad', 0) + 1
                        failures.append(f"fence clip @t={t}: {hit['subject']} {hit['mesh']} vs {hit['obstacle']}")
            elif section == 'food':
                if c.get(S.get('present_key', 'nug')):
                    stats['nug_frames'] = stats.get('nug_frames', 0) + 1
                    tp = S['tip']
                    if c.get(tp['a']):
                        d = dist(c[tp['a']], c[tp['b']])
                        stats['nug_tip_max'] = max(stats.get('nug_tip_max', 0), d)
                        if d > tp['max']:
                            failures.append(f"skewer tip outside nugget: {d:.3f}m @t={t:.2f}")
                    bn = S['bone']
                    if c.get(bn['key'], 99) < bn['min']:
                        stats['nug_bone_min'] = min(stats.get('nug_bone_min', 99), c[bn['key']])
                        failures.append(f"finger through nugget: {c[bn['key']]:.3f}m @t={t:.2f}")
                    else:
                        stats['nug_bone_min'] = min(stats.get('nug_bone_min', 99), c[bn['key']])
            elif section == 'wrist':
                for key, w in (c.get('wrist') or {}).items():
                    stats['wrist_applied_max'] = max(stats.get('wrist_applied_max', 0), w['appliedDeg'])
                    stats['wrist_demand_max'] = max(stats.get('wrist_demand_max', 0), w['demandDeg'])
                    if w['appliedDeg'] > S['applied_max_deg']:
                        failures.append(f"wrist twist over physio limit: {key} {w['appliedDeg']:.0f}° @t={t:.2f}")
                    if w['palmDot'] > S['palm_dot_max']:
                        failures.append(f"palm not perpendicular to forearm: {key} {w['palmDot']:.2f} @t={t:.2f}")
            elif section == 'tray':
                boxes = c.get('boxPos') or {}
                for e in S['entries']:
                    k = (c.get('trayK') or {}).get(e['key'], 0)
                    if k > S['k_min'] and boxes.get(e['box']) and (c.get('boxVis') or {}).get(e['box'], True):
                        d = dist(c['hands'][e['actor']][e['side']], boxes[e['box']])
                        stats['tray_leak_max'] = max(stats.get('tray_leak_max', 0), d)
                        if d > e['lim']:
                            failures.append(f"tray palm off box: {e['key']} {d:.3f}m @t={t:.2f}")
            elif section == 'supporter':
                boxes = c.get('boxPos') or {}
                for box, pos in boxes.items():
                    if not (c.get('boxVis') or {}).get(box, True):
                        continue
                    win = S['support_win'].get(box)
                    if not win or not (win[0] <= t <= win[1]):
                        continue
                    tr = S.get('transit', {}).get(box)
                    if tr and tr[0] <= t <= tr[1]:
                        continue
                    actor = S['actor_of'][box]
                    best = min(dist(h, pos) for h in c['hands'][actor].values())
                    stacked = S.get('stacked', {}).get(box)
                    if stacked and t < stacked['until']:
                        below = boxes.get(stacked['below'])
                        if below:
                            best = dist(pos, below)
                    lim = S['lims'][box]
                    stats['unsupported_min'] = min(stats.get('unsupported_min', 99), best)
                    if best > lim:
                        failures.append(f"box without supporter: {box} {best:.3f}m @t={t:.2f}")
            elif section == 'lid':
                for box, ang in (c.get('lidAngle') or {}).items():
                    prevA = prev_box.get('lid_' + box)
                    if prevA is not None and abs(ang - prevA) > S['angle_eps']:
                        d = (c.get('lidTabDist') or {}).get(box, 99)
                        stats['lid_far_max'] = max(stats.get('lid_far_max', 0), d)
                        if d > S['max_dist']:
                            failures.append(f"lid moves without hand: {box} hand {d:.3f}m @t={t:.2f}")
                    prev_box['lid_' + box] = ang
            elif section == 'pinch':
                if S['window'][0] <= t <= S['window'][1] and c.get(S['a']) and c.get(S['point']) and c.get(S['b']):
                    p = c[S['point']]; a = c[S['a']]; b = c[S['b']]
                    ab = [b[i] - a[i] for i in range(3)]
                    apv = [p[i] - a[i] for i in range(3)]
                    L2 = sum(x * x for x in ab)
                    u = max(0, min(1, sum(apv[i] * ab[i] for i in range(3)) / max(L2, 1e-12)))
                    d = dist(p, [a[i] + ab[i] * u for i in range(3)])
                    stats['pinch_min'] = min(stats.get('pinch_min', 99), d)
                    stats['pinch_max'] = max(stats.get('pinch_max', 0), d)
                    if d < S['min'] or d > S['max']:
                        failures.append(f"skewer axis off pinch zone: {d:.3f}m @t={t:.2f}")
            elif section == 'dual':
                bp = (frame.get('bento') or {}).get('positions') or {}
                for e in S['entries']:
                    box = bp.get(e['box'])
                    if not box or not (e['window'][0] <= t <= e['window'][1]):
                        continue
                    for side, hand in c['hands'][e['actor']].items():
                        d = dist(hand, box)
                        stats['carry_dual_max'] = max(stats.get('carry_dual_max', 0), d)
                        if d > e['max']:
                            failures.append(f"two-hand carry: {e['actor']} {side} off box {d:.3f}m @t={t:.2f}")
            elif section == 'place':
                bp = (frame.get('bento') or {}).get('positions') or {}
                for e in S['entries']:
                    box = bp.get(e['box'])
                    if box and e['window'][0] <= t <= e['window'][1]:
                        d = dist(c['hands'][e['actor']][e['side']], box)
                        stats['place_max'] = max(stats.get('place_max', 0), d)
                        if d > e['lim']:
                            failures.append(f"place without hand: {e['actor']} {d:.3f}m @t={t:.2f}")
            elif section == 'continuity':
                bp = (frame.get('bento') or {}).get('positions') or {}
                for e in S['entries']:
                    box = bp.get(e['box'])
                    prev = prev_box.get(e['box'])
                    tick = math.floor(t * tick_hz + 1e-6)
                    if box and prev:
                        step_d = dist(box, prev)
                        if e['window'][0] <= t < e['down_t']:
                            if tick != prev_box.get(e['box'] + '_tick'):
                                stats['place_step_max'] = max(stats.get('place_step_max', 0), step_d)
                                if step_d > e['step_max']:
                                    failures.append(f"box jumps during placement: {e['box']} {step_d:.3f}m @t={t:.2f}")
                        elif t >= e['down_t'] and step_d > e['down_step_max']:
                            stats['down_step_max'] = max(stats.get('down_step_max', 0), step_d)
                            failures.append(f"box not static after down: {e['box']} {step_d:.4f}m @t={t:.2f}")
                    if box and tick != prev_box.get(e['box'] + '_tick'):
                        prev_box[e['box']] = box
                        prev_box[e['box'] + '_tick'] = tick
            elif section == 'gait':
                loc = frame.get('locomotion') or {}
                for actor, G in S['actors'].items():
                    L = loc.get(actor)
                    if not L or L.get('kind') != 'walk':
                        if gait_bout.get(actor):
                            gait_bouts.setdefault(actor, []).append(gait_bout.pop(actor))
                        gait_prev[actor] = None
                        continue
                    bout = gait_bout.get(actor)
                    if not bout:
                        bout = gait_bout[actor] = {'t0': t, 't1': t, 'speeds': [], 'bob_max': 0., 'falls': 0}
                    bout['t1'] = t
                    bout['bob_max'] = max(bout['bob_max'], abs(L.get('bob') or 0))
                    prev = gait_prev.get(actor)
                    if prev:
                        dt = t - prev['t']
                        if dt > 1e-6:
                            spd = math.hypot(L['root'][0] - prev['root'][0],
                                             L['root'][2] - prev['root'][2]) / dt
                            bout['speeds'].append(spd)
                            stats[f'gait_speed_max_{actor}'] = max(stats.get(f'gait_speed_max_{actor}', 0), spd)
                            if spd > G['speed_max']:
                                failures.append(f"gait too fast: {actor} {spd:.2f}m/s @t={t:.2f}")
                            if L.get('step', 0) > prev['step']:
                                bout['falls'] += L['step'] - prev['step']
                    gait_prev[actor] = {'t': t, 'root': L['root'], 'step': L.get('step', 0)}
            elif section == 'limb_attach':
                arms = c.get('arms') or {}
                axis = c.get('torsoAxis') or {}
                for actor, G in S['actors'].items():
                    a = arms.get(actor)
                    ax = axis.get(actor)
                    if not a or not ax:
                        continue
                    down = [ax[0][i] - ax[1][i] for i in range(3)]
                    dl = math.sqrt(sum(x * x for x in down)) or 1
                    down = [x / dl for x in down]
                    for side, pts in a.items():
                        sh, el = pts[0], pts[1]
                        ua = [el[i] - sh[i] for i in range(3)]
                        ul = math.sqrt(sum(x * x for x in ua)) or 1
                        cos = sum(ua[i] * down[i] for i in range(3)) / ul
                        elev = math.degrees(math.acos(max(-1., min(1., cos))))
                        stats[f'limb_elev_max_{actor}'] = max(stats.get(f'limb_elev_max_{actor}', 0), elev)
                        if elev > G['max_elev_deg']:
                            failures.append(f"arm raised past shoulder line: {actor} {side} {elev:.0f}° @t={t:.2f}")
                        ap = [sh[i] - ax[1][i] for i in range(3)]  # 肩点到躯干轴线的距离（漂移/脱嵌）
                        along = sum(ap[i] * down[i] for i in range(3))
                        d = dist(sh, [ax[1][i] + down[i] * along for i in range(3)])
                        stats[f'limb_shoulder_axis_max_{actor}'] = max(
                            stats.get(f'limb_shoulder_axis_max_{actor}', 0), d)
                        if d > G['max_shoulder_axis']:
                            failures.append(f"shoulder off torso axis: {actor} {side} {d:.3f}m @t={t:.2f}")
            elif section == 'worn_prop':
                w = frame.get(S.get('state_key', 'worn'))
                if w:
                    stats['worn_frames'] = stats.get('worn_frames', 0) + 1
                    for hit in w['hits']:
                        stats['worn_bad'] = stats.get('worn_bad', 0) + 1
                        failures.append(f"worn prop clip @t={t}: {hit['subject']} {hit['mesh']} vs {hit['obstacle']}")
            elif section == 'grip':
                for e in S['entries']:
                    g = (c.get('grip') or {}).get(e['key'])
                    if not g or not (e['window'][0] <= t <= e['window'][1]):
                        continue
                    stats['grip_frames'] = stats.get('grip_frames', 0) + 1
                    stats['grip_palm_gap_max'] = max(stats.get('grip_palm_gap_max', 0), abs(g['palmGap']))
                    stats['grip_finger_worst'] = max(stats.get('grip_finger_worst', 0), g['fingerMin'])
                    if not g['inFoot'] or abs(g['palmGap']) > e['palm_max']:
                        failures.append(f"tray palm off box bottom: {e['key']} gap={g['palmGap']:.4f} "
                                        f"inFoot={g['inFoot']} @t={t:.2f}")
                    if g['fingerMin'] > e['finger_max']:
                        failures.append(f"no finger on box wall: {e['key']} {g['fingerMin']:.3f}m @t={t:.2f}")
            elif section == 'palm_semantic':
                for e in S['entries']:
                    p = (c.get('palmIn') or {}).get(e['key'])
                    if not p or p.get('k', 0) < S.get('k_min', .5):
                        continue
                    stats['palm_frames'] = stats.get('palm_frames', 0) + 1
                    stats['palm_dot_min'] = min(stats.get('palm_dot_min', 99), p['dot'])
                    if p['dot'] < e['min_dot']:
                        failures.append(f"palm not facing torso on bring-to-mouth: {e['key']} "
                                        f"dot={p['dot']:.2f} @t={t:.2f}")
            elif section == 'hand_body_mesh':
                hb = frame.get(S.get('state_key', 'handBody'))
                if not hb or not (S['window'][0] <= t <= S['window'][1]):
                    continue
                stats['handbody_frames'] = stats.get('handbody_frames', 0) + 1
                for hit in hb['hits']:
                    ok = any(r['subject'] == hit['subject'] and r['obstacle'] == hit['obstacle']
                             and r['window'][0] <= t <= r['window'][1] for r in S.get('allowed', []))
                    if not ok:
                        stats['handbody_bad'] = stats.get('handbody_bad', 0) + 1
                        failures.append(f"hand embedded in body: {hit['subject']} "
                                        f"vs {hit['obstacle']} @t={t:.2f}")
            elif section == 'rest_support':
                if not (S['window'][0] <= t <= S['window'][1]):
                    continue
                stats['rest_frames'] = stats.get('rest_frames', 0) + 1
                hr = c.get('handRest') or {}
                arms_c = c.get('arms') or {}
                for actor in S['actors']:
                    for side, g in (hr.get(actor) or {}).items():
                        key = f'{actor}:{side}'
                        hand = c['hands'][actor][side]
                        hist = rest_prev.setdefault(key, [])
                        hist.append((t, hand))
                        while hist and hist[0][0] < t - .12:
                            hist.pop(0)
                        if t - hist[0][0] < .06:
                            continue  # 攒不够观察窗不判
                        speed = dist(hand, hist[0][1]) / (t - hist[0][0])
                        still = speed < S['max_speed'] and hand[1] < S['max_y']
                        # 持续静息判定：攒够 .35s 低速帧才判（条目边界混合/缓动尾不算定格）
                        if speed < S['max_speed']:
                            rest_prev[key + ':stillN'] = rest_prev.get(key + ':stillN', 0) + 1
                        else:
                            rest_prev[key + ':stillN'] = 0
                        if rest_prev[key + ':stillN'] < max(2, round(.35 * 30)):
                            continue
                        if not still or hand[1] >= S['max_y']:
                            continue  # 活动中/高举的手不判定静息支撑
                        if any((r.get('hand') in (None, key)) and r['window'][0] <= t <= r['window'][1]
                               for r in S.get('exclude', [])):
                            continue
                        stats['rest_still_frames'] = stats.get('rest_still_frames', 0) + 1
                        stats['rest_gap_max'] = max(stats.get('rest_gap_max', 0), g['support'])
                        if g['support'] <= S['gap_max']:
                            continue  # 有接触支撑（贴腿/贴盒）
                        # 垂臂替代判据：前臂近竖直下垂=重力悬挂读数成立（掌心朝腿、无悬空桌）
                        a = (arms_c.get(actor) or {}).get(side)
                        if a:
                            f = [a[2][i] - a[1][i] for i in range(3)]
                            fl = math.sqrt(sum(x * x for x in f)) or 1
                            hang_deg = math.degrees(math.acos(max(-1., min(1., -f[1] / fl))))
                            stats['rest_hang_deg_max'] = max(stats.get('rest_hang_deg_max', 0), hang_deg)
                            if hang_deg <= S.get('hang_deg', 25):
                                continue
                        failures.append(f"resting hand unsupported: {key} gap={g['support']:.3f}m @t={t:.2f}")
            elif section == 'state_consistency':
                pass  # 迁移/触发/事件/行为规则需要全时间轴——finalize 段统一做

    if not args.door_only:
        if C.get('whitelist') and stats.get('bento_frames', 0) < C['whitelist'].get('frame_min', 100):
            failures.append('bento probe missing or too sparse: run render with the mesh-probe query flag')
        if C.get('env') and stats.get('env_frames', 0) < C['env'].get('frame_min', 100):
            failures.append('fence probe missing: run render with the mesh-probe query flag')
        if C.get('food') and stats.get('nug_frames', 0) < C['food'].get('frame_min', 10):
            failures.append('food probe missing: skewer window not sampled')
        if C.get('bite') and stats['bite_min'] > C['bite']['max']:
            failures.append(f"skewer never reaches mouth: min {stats['bite_min']:.3f}m")
        if C.get('worn_prop') and stats.get('worn_frames', 0) < C['worn_prop'].get('frame_min', 100):
            failures.append('worn probe missing or too sparse: run render with the mesh-probe query flag')
        if C.get('grip') and stats.get('grip_frames', 0) < C['grip'].get('frame_min', 50):
            failures.append('grip probe missing or too sparse: tray windows not sampled')
        if C.get('palm_semantic') and stats.get('palm_frames', 0) < C['palm_semantic'].get('frame_min', 20):
            failures.append('palm-semantic probe missing: no bring-to-mouth frames logged')
        if C.get('hand_body_mesh') and stats.get('handbody_frames', 0) < C['hand_body_mesh'].get('frame_min', 100):
            failures.append('hand-body probe missing or too sparse')
        if C.get('rest_support') and stats.get('rest_still_frames', 0) < C['rest_support'].get('still_frame_min', 20):
            failures.append('rest-support probe found no still hands to validate')
        if C.get('state_consistency'):
            state_consistency_pass(C['state_consistency'], data, stats, failures)
        if C.get('gait'):
            for actor, G in C['gait']['actors'].items():
                bouts = list(gait_bouts.get(actor, []))
                if gait_bout.get(actor):
                    bouts.append(gait_bout[actor])
                if not bouts:
                    failures.append(f'gait probe missing: {actor} never walks')
                    continue
                spd_all = sorted(s for b in bouts for s in b['speeds'])
                if spd_all:
                    stats[f'gait_speed_p50_{actor}'] = round(spd_all[len(spd_all) // 2], 3)
                    stats[f'gait_speed_p95_{actor}'] = round(spd_all[min(len(spd_all) - 1, int(len(spd_all) * .95))], 3)
                for b in bouts:
                    dur = b['t1'] - b['t0']
                    if dur < .4:
                        continue
                    avg = sum(b['speeds']) / max(1, len(b['speeds']))
                    stats[f'gait_avg_min_{actor}'] = round(min(avg, stats.get(f'gait_avg_min_{actor}', 99)), 3)
                    if avg < G['avg_min']:
                        failures.append(f"gait too slow: {actor} avg {avg:.2f}m/s @t={b['t0']:.2f}")
                    if b['bob_max'] < G['bob_min']:
                        failures.append(f"gait gliding (no bob): {actor} bob {b['bob_max']:.3f} @t={b['t0']:.2f}")
                    cad = b['falls'] / dur
                    stats[f'gait_cadence_min_{actor}'] = round(min(cad, stats.get(f'gait_cadence_min_{actor}', 99)), 2)
                    stats[f'gait_cadence_max_{actor}'] = round(max(cad, stats.get(f'gait_cadence_max_{actor}', 0)), 2)
                    if cad < G['cadence'][0] or cad > G['cadence'][1]:
                        failures.append(f"gait cadence off: {actor} {cad:.2f}steps/s @t={b['t0']:.2f}")

    if args.door_only:
        stats = {k: v for k, v in stats.items() if k.startswith('door_')}
    report = {'passed': not failures, 'stats': stats, 'failures': failures,
              'scope': C.get('scope', DEFAULT_SCOPE)}
    args.trace.with_name('contact_validation.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(stats, indent=1))
    if failures:
        print(f"FAIL {len(failures)} contact violations")
        for f in failures[:20]:
            print(' ', f)
        raise SystemExit(2)
    print('contact check: all assertions passed')


if __name__ == '__main__':
    main()
