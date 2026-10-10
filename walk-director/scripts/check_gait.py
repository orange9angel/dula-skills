#!/usr/bin/env python3
"""步态朝向一致性检查（螃蟹走检测）。

逻辑/运动学类问题（"看着不对"）技术检查管不了，要转成可计算的物理量：
本脚本检查**朝向向量 × 根速度向量的夹角**——正常行走时二者同向（夹角≈0），
螃蟹走（面朝观众、身体平移）时夹角持续接近 90°。

输入 trace 是通用 JSON（可由任何管线的渲染器/采样器导出）：
  {"fps": 60, "frames": [{"t": 0.0, "root": [x, y, z], "yaw": 0.0}, ...]}
  - root：角色根骨世界坐标（米）；yaw：朝向角（弧度，yaw=0 面朝 +Z，yaw=π/2 面朝 +X）
  - 输入只包含一段连续的普通前进。侧移、后退和转身应由调用方预先排除；
    本检查无法识别表演意图，会把持续反向移动同样报警。
    仅在 |速度| 超阈值且夹角持续超阈值时报警（默认 >60° 持续 >0.3s）。

用法：
  check_gait.py trace.json [--speed-min 0.15] [--angle-max 60] [--min-duration 0.3]
退出码：0 全绿；1 发现螃蟹走区间；2 输入错误。
"""
import argparse
import json
import math
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description='朝向×速度夹角的螃蟹走检测')
    ap.add_argument('trace', help='trace JSON（{fps, frames:[{t, root, yaw}]}）')
    ap.add_argument('--speed-min', type=float, default=0.15, help='根速度阈值 m/s（低于视为站立/表演，不判定）')
    ap.add_argument('--angle-max', type=float, default=60.0, help='朝向-速度夹角阈值（度），超过计入螃蟹帧')
    ap.add_argument('--min-duration', type=float, default=0.3, help='连续超阈值的最短报警时长（秒）')
    ap.add_argument('--window', type=float, default=0.2,
                    help='速度/位移的滑窗时长（秒）。一拍二管线的根位置按 12fps 量化，'
                         '逐帧差分得到的是梳状脉冲，必须加窗')
    args = ap.parse_args()

    try:
        data = json.load(open(args.trace, encoding='utf-8'))
    except OSError as exc:
        print(f'ERROR: 读不到 trace：{exc}', file=sys.stderr)
        return 2
    frames = data.get('frames')
    if not isinstance(frames, list) or len(frames) < 3:
        print('ERROR: trace 里 frames 不足', file=sys.stderr)
        return 2
    if any('yaw' not in f or f.get('yaw') is None or 'root' not in f for f in frames):
        print('ERROR: trace 帧缺 root/yaw 字段（先在渲染器里补采样导出）', file=sys.stderr)
        return 2

    crab = []  # 逐帧 bool
    speeds = []
    n = len(frames)
    half = args.window / 2
    for i, f in enumerate(frames):
        # 滑窗位移：窗口内的总位移 ÷ 窗口时长，对抗姿态量化的梳状速度
        j = i
        while j > 0 and frames[j]['t'] > f['t'] - half:
            j -= 1
        k = i
        while k < n - 1 and frames[k]['t'] < f['t'] + half:
            k += 1
        a, b = frames[j], frames[k]
        dt = max(b['t'] - a['t'], 1e-6)
        vx = (b['root'][0] - a['root'][0]) / dt
        vz = (b['root'][2] - a['root'][2]) / dt
        speed = math.hypot(vx, vz)
        speeds.append(speed)
        if speed < args.speed_min:
            crab.append(False)
            continue
        heading = (math.sin(f['yaw']), math.cos(f['yaw']))
        dot = (vx * heading[0] + vz * heading[1]) / speed
        angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        crab.append(angle > args.angle_max)

    # 连续螃蟹帧 → 区间（按 t 聚合，允许 ≤1 帧的正常帧毛刺不打断区间）
    intervals = []
    start = None
    glitch = 0
    for i, c in enumerate(crab):
        if c:
            if start is None:
                start = i
            glitch = 0
        elif start is not None:
            glitch += 1
            if glitch > 1:
                end = i - glitch
                if frames[end]['t'] - frames[start]['t'] >= args.min_duration:
                    intervals.append((frames[start]['t'], frames[end]['t']))
                start = None
                glitch = 0
    if start is not None and frames[len(frames) - 1]['t'] - frames[start]['t'] >= args.min_duration:
        intervals.append((frames[start]['t'], frames[len(frames) - 1]['t']))

    max_speed = max(speeds)
    print(f'帧数 {len(frames)}，根峰值速度 {max_speed:.2f} m/s，'
          f'阈值：速度>{args.speed_min} m/s 且 夹角>{args.angle_max}° 持续 >{args.min_duration}s')
    if intervals:
        print(f'❌ 螃蟹走区间 {len(intervals)} 段：')
        for a, b in intervals:
            print(f'   {a:6.2f}s – {b:6.2f}s（{b - a:.2f}s）')
        return 1
    print('✅ 全绿：移动段朝向与速度方向一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
