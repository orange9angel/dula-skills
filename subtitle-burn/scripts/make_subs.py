#!/usr/bin/env python3
"""subtitle-burn — 字幕组风格双语字幕生成与烧入。
输入事件 JSON（英文由代理翻译填写），输出字幕组风 ASS；可选直接 ffmpeg 烧入视频。
用法:
  make_subs.py --events subs.json --ass-out out.ass
  make_subs.py --events subs.json --ass-out out.ass --video in.mp4 --out-video out.mp4
events JSON 格式见 SKILL.md。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

# 字幕组角色分色盘（ABGR，按出场顺序循环取用）
PALETTE = [
    "&H00D0E8FF",  # 淡金
    "&H00FFE8D0",  # 淡青
    "&H00D0FFD0",  # 淡绿
    "&H00FFD0F0",  # 淡粉
    "&H00C0E0FF",  # 浅橘
    "&H00E8D0FF",  # 淡紫
]

HEADER = """[Script Info]
Title: {project} — {group}
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""

STYLE_CN = ("Style: CN_{idx},{cn_font},44,{color},&H000000FF,&H8C140F0F,&H8C000000,"
            "-1,0,0,0,100,100,0.5,0,1,3,0.8,2,40,40,96,1\n")
STYLE_EN = ("Style: EN,Calibri,26,&H0000D8FF,&H000000FF,&H8C140F0F,&H8C000000,"
            "0,-1,0,0,100,100,0,0,1,2.4,0.6,2,40,40,56,1\n")
STYLE_GROUP = ("Style: Group,{cn_font},40,&H00FFFFFF,&H000000FF,&H8C00A078,&H8C000000,"
               "-1,0,0,0,100,100,2,0,1,3.2,1.2,8,40,40,40,1\n")
STYLE_GSUB = ("Style: GroupSub,Calibri,22,&H00D8E4E4,&H000000FF,&H8C140F0F,&H8C000000,"
              "0,-1,0,0,100,100,1,0,1,2,0.6,8,40,40,88,1\n")

EVENTS_HEADER = ("\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR,"
                 " MarginV, Effect, Text\n")


def ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(doc: dict, cn_font: str) -> str:
    group = doc.get("group", "Dula 字幕组")
    project = doc.get("project", "")
    speakers: list[str] = []
    for ev in doc["events"]:
        if ev["speaker"] not in speakers:
            speakers.append(ev["speaker"])

    out = HEADER.format(project=project, group=group)
    style_of = {}
    for i, spk in enumerate(speakers):
        style_of[spk] = f"CN_{i}"
        out += STYLE_CN.format(idx=i, cn_font=cn_font, color=PALETTE[i % len(PALETTE)])
    out += STYLE_EN + STYLE_GROUP.format(cn_font=cn_font) + STYLE_GSUB + EVENTS_HEADER

    if group:
        out += (f"Dialogue: 1,0:00:00.10,0:00:02.80,Group,,0,0,0,,"
                f"{{\\fad(600,800)}}{group}\n")
    if project:
        out += (f"Dialogue: 1,0:00:00.10,0:00:02.80,GroupSub,,0,0,0,,"
                f"{{\\fad(600,800)}}{project}\n")
    for ev in doc["events"]:
        start, end = ts(ev["start"]), ts(ev["end"])
        fade = ev.get("fade", "400,500")
        out += (f"Dialogue: 0,{start},{end},{style_of[ev['speaker']]},,0,0,0,,"
                f"{{\\fad({fade})}}{ev['cn']}\n")
        if ev.get("en"):
            out += (f"Dialogue: 0,{start},{end},EN,,0,0,0,,"
                    f"{{\\fad({fade})}}{ev['en']}\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="字幕组风格双语字幕生成/烧入")
    ap.add_argument("--events", required=True, type=Path, help="事件 JSON")
    ap.add_argument("--ass-out", required=True, type=Path)
    ap.add_argument("--cn-font", default="Microsoft YaHei")
    ap.add_argument("--video", type=Path, help="烧入的源视频（净版母带）")
    ap.add_argument("--out-video", type=Path, help="烧入后的输出视频")
    args = ap.parse_args()

    doc = json.loads(args.events.read_text(encoding="utf-8"))
    args.ass_out.parent.mkdir(parents=True, exist_ok=True)
    args.ass_out.write_text(build_ass(doc, args.cn_font), encoding="utf-8")
    print(f"ass: {args.ass_out}")

    if args.video or args.out_video:
        if not (args.video and args.out_video):
            sys.exit("--video 与 --out-video 必须同时给")
        # ffmpeg ass 滤镜路径：Windows 盘符冒号要转义
        ass_path = str(args.ass_out.resolve()).replace("\\", "/").replace(":", "\\:")
        cmd = [
            "ffmpeg", "-loglevel", "error", "-y", "-i", str(args.video),
            "-vf", f"ass='{ass_path}'",
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "copy", str(args.out_video),
        ]
        subprocess.run(cmd, check=True)
        print(f"video: {args.out_video}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
