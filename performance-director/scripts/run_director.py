#!/usr/bin/env python3
"""
Performance Director — 基于语义优化 Dula 剧本中的表情和动作。

用法：
    python run_director.py <episode-dir> [--output <path>]

示例：
    cd dula-story
    python ../dula-skills/performance-director/scripts/run_director.py \
        ./episodes/tom_jerry_midnight_snack \
        --output ./episodes/tom_jerry_midnight_snack/script.story.perf
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


# ── 表情语义映射 ──
# 关键词 → 候选表情（按优先级）
EXPRESSION_KEYWORDS: Dict[str, List[str]] = {
    # 正面情绪
    "开心": ["FaceHappy"],
    "高兴": ["FaceHappy"],
    "哈哈": ["FaceHappy"],
    "谢谢": ["FaceHappy"],
    "棒": ["FaceHappy"],
    # 得意/试探/挑衅
    "得意": ["FaceSmirk"],
    "坏笑": ["FaceSmirk"],
    "嘿嘿": ["FaceSmirk"],
    "试探": ["FaceSmirk"],
    "挑衅": ["FaceSmirk"],
    "嘲": ["FaceSmirk"],
    "轻蔑": ["FaceSmirk"],
    "不屑": ["FaceSmirk"],
    # 使坏/捉弄
    "使坏": ["FaceMischief"],
    "捉弄": ["FaceMischief"],
    "偷笑": ["FaceMischief"],
    "坏主意": ["FaceMischief"],
    # 大获全胜/得意洋洋
    "洋洋得意": ["FaceGloat"],
    "大获全胜": ["FaceGloat"],
    "得逞": ["FaceGloat"],
    # 喜剧震惊
    "惊呆": ["FaceShockComedy"],
    "吓呆": ["FaceShockComedy"],
    "目瞪口呆": ["FaceShockComedy"],
    # 坚定
    "坚定": ["FaceDetermined"],
    "决心": ["FaceDetermined"],
    "一定": ["FaceDetermined"],
    "自己": ["FaceDetermined"],
    # 生气
    "生气": ["FaceAngry"],
    "怒": ["FaceAngry"],
    "可恶": ["FaceAngry"],
    "站住": ["FaceAngry"],
    "混蛋": ["FaceAngry"],
    # 惊讶/害怕
    "惊讶": ["FaceSurprised"],
    "啊": ["FaceSurprised"],
    "怎么": ["FaceSurprised"],
    "完了": ["FaceSurprised"],
    "糟": ["FaceSurprised"],
    # 疼痛/狼狈
    "疼": ["FacePain"],
    "痛": ["FacePain"],
    "哎哟": ["FacePain"],
    # 困惑
    "奇怪": ["FaceConfused"],
    "怎么回": ["FaceConfused"],
    "什么": ["FaceConfused"],
    # 悲伤
    "难过": ["FaceSad"],
    "伤心": ["FaceSad"],
    "呜": ["FaceSad"],
}


# ── 动作语义映射 ──
# 关键词 → 候选动作（按优先级）
ACTION_KEYWORDS: Dict[str, List[str]] = {
    # 打招呼/友好
    "你好": ["WaveHand", "Nod"],
    "大家好": ["WaveHand"],
    "见面": ["MouseOffer"],
    "分一半": ["MouseOffer"],
        # 拒绝/否定
    "不": ["ShakeHead", "CrossArms"],
    "不能": ["CrossArms", "ShakeHead"],
    "没": ["CrossArms", "ShakeHead"],
    "拒绝": ["CrossArms"],
    # 安静/保密
    "嘘": ["CartoonShush"],
    "安静": ["CartoonShush"],
    "秘密": ["CartoonShush"],
    # 挑衅/得意
    "得意": ["MouseTaunt", "HandsOnHips"],
    "挑衅": ["MouseTaunt"],
    "嘲": ["MouseTaunt"],
    "多谢": ["MouseTaunt"],
    # 攻击/追逐（"往哪跑"是反问，不触发追逐）
    "站住": ["CatPounce"],
    r"(?<!哪|哪里|往哪|往哪里)跑": ["CatPounce", "MouseScamper"],
    "追": ["CatPounce"],
    "抓": ["CatCatchStack"],
    "扑": ["CatPounce"],
    # 与蛋糕/道具互动
    r"推.*蛋糕": ["MousePushCake"],
    r"伸手.*蛋糕|拿.*蛋糕|够.*蛋糕": ["CatReachCake"],
    r"抓.*蛋糕": ["CatGrab"],
    r"糊.*脸|拍.*脸": ["CatPieFace"],
    # 滑倒/失败
    "滑": ["CatSlip"],
    "滑倒": ["CatSlip"],
    "摔倒": ["FlailArms", "CatSlip"],
    # 躲闪/告别
    "躲": ["MouseDodge"],
    "闪": ["MouseDodge"],
    "再见": ["MouseWaveGoodbye"],
    "拜拜": ["MouseWaveGoodbye"],
    # 偷偷摸摸
    " sneak": ["CatSneak"],
    "偷偷": ["CatSneak"],
    "一口": ["CatSneak"],
    "知道": ["CatSneak"],
    # 陷阱/压制
    "看你": ["CatTrapPress"],
    "跑不了": ["CatTrapPress"],
    # 失败/狼狈
    "完了": ["CatDoom"],
    "糟": ["CatDoom"],
    "摔": ["FlailArms"],
    "啊": ["SurprisedJump"],
}


# ── 角色特化规则 ──
# 对特定角色，覆盖通用映射
CHARACTER_OVERRIDES: Dict[str, Dict[str, List[str]]] = {
    "Tom": {
        "expressions": {
            "得意": ["FaceSmirk"],
            "生气": ["FaceAngry"],
            "惊讶": ["FaceSurprised"],
            "完了": ["FaceSurprised"],
            "使坏": ["FaceMischief"],
            "洋洋得意": ["FaceGloat"],
            "惊呆": ["FaceShockComedy"],
        },
        "actions": {
            "不": ["CrossArms"],
            "不能": ["CrossArms"],
            "没": ["CrossArms"],
            "拒绝": ["CrossArms"],
            "嘘": ["CartoonShush"],
            "安静": ["CartoonShush"],
            "攻击": ["CatPounce"],
            "追逐": ["CatPounce"],
            "偷偷": ["CatSneak"],
            "陷阱": ["CatTrapPress"],
            "失败": ["CatDoom", "FlailArms"],
            "狼狈": ["FlailArms"],
            "蛋糕": ["CatReachCake"],
            "滑": ["CatSlip"],
            "摔倒": ["CatSlip", "FlailArms"],
        },
    },
    "Jerry": {
        "expressions": {
            "得意": ["FaceSmirk"],
            "挑衅": ["FaceSmirk"],
            "开心": ["FaceHappy"],
            "拒绝": ["FaceDetermined"],
            "见面": ["FaceSmirk"],
            "多谢": ["FaceSmirk"],
            "使坏": ["FaceMischief"],
            "洋洋得意": ["FaceGloat"],
            "惊呆": ["FaceShockComedy"],
        },
        "actions": {
            "见面": ["MouseOffer"],
            "分一半": ["MouseOffer"],
            "得意": ["MouseTaunt"],
            "挑衅": ["MouseTaunt"],
            "多谢": ["MouseTaunt"],
            "自己": ["MouseTaunt"],
            "嘘": ["CartoonShush"],
            "逃跑": ["MouseScamper"],
            "跑": ["MouseScamper"],
            "推": ["MousePushCake"],
            "躲": ["MouseDodge"],
            "闪": ["MouseDodge"],
            "再见": ["MouseWaveGoodbye"],
            "拜拜": ["MouseWaveGoodbye"],
        },
    },
}


# ── 剧本解析 ──
@dataclass
class StoryEntry:
    index: int
    start: str
    end: str
    lines: List[str] = field(default_factory=list)
    speaker: Optional[str] = None
    text: str = ""
    action: Optional[str] = None
    face: Optional[str] = None
    is_spoken: bool = False
    # 说话行中的其他标签（Voice/Camera/Position 等），重建时保留
    other_tags: List[str] = field(default_factory=list)
    # 原说话行的所有标签（含 action/face/other），用于重建
    raw_tags: List[str] = field(default_factory=list)
    speaker_line_index: int = -1


def _extract_tags(line: str) -> List[str]:
    """提取行内所有 {...} 标签。"""
    return re.findall(r"\{[^}]+\}", line)


def _find_tag(tags: List[str], prefix: str) -> Optional[str]:
    """从标签列表中找出匹配前缀的标签内容（不含大括号）。"""
    for tag in tags:
        inner = tag[1:-1]
        if inner.startswith(prefix):
            return inner
    return None


def _is_namespace_tag(tag_inner: str) -> bool:
    """判断标签是否是命名空间标签（如 Animation:、Voice:、Camera:），而非身体动作。"""
    namespaces = {
        "Animation:", "Camera:", "Music:", "SFX:", "Voice:", "Position:", "Prop:",
        "Transition:", "Event:", "Ball:", "Dunk:", "Hitstop:", "Combat:",
        "SceneDirector:", "Exaggeration:",
    }
    for ns in namespaces:
        if tag_inner.startswith(ns):
            return True
    return False


def parse_story(story_path: Path) -> List[StoryEntry]:
    """解析 .story 文件为 StoryEntry 列表，正确分离动作、表情和其他标签。"""
    content = story_path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", content.strip())
    entries: List[StoryEntry] = []

    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        if not lines[0].strip().isdigit():
            continue
        m = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1],
        )
        if not m:
            continue

        entry = StoryEntry(
            index=int(lines[0].strip()),
            start=m.group(1),
            end=m.group(2),
            lines=lines[2:],
        )

        # 找说话行
        for idx, ln in enumerate(entry.lines):
            speaker_match = re.match(r"\[(\w+)\]\s*(.*)", ln)
            if not speaker_match:
                continue

            entry.speaker = speaker_match.group(1)
            rest = speaker_match.group(2).strip()
            tags = _extract_tags(rest)
            entry.raw_tags = tags
            entry.speaker_line_index = idx
            entry.is_spoken = True

            # 第一个非命名空间标签是身体动作
            action_set = False
            other_tags: List[str] = []
            for tag in tags:
                inner = tag[1:-1]
                if not action_set and not _is_namespace_tag(inner):
                    entry.action = inner
                    action_set = True
                else:
                    other_tags.append(tag)

            # 从其他标签中提取 Animation:FaceXxx
            for tag in other_tags:
                inner = tag[1:-1]
                fm = re.match(r"Animation:(Face\w+)\s*\|character=([^}]+)", inner)
                if fm:
                    entry.face = fm.group(1)
                    break

            # 剩余的 other_tags 去掉 face 标签
            entry.other_tags = [
                tag for tag in other_tags
                if not re.match(r"\{Animation:Face\w+\s*\|character=([^}]+)\}", tag)
            ]

            # 台词文本：去掉所有标签后的剩余部分
            text_part = rest
            for tag in tags:
                text_part = text_part.replace(tag, "", 1)
            entry.text = text_part.strip()
            break

        entries.append(entry)

    return entries


def render_entry(entry: StoryEntry) -> str:
    """把 StoryEntry 渲染回 .story 文本块。"""
    lines = [str(entry.index), f"{entry.start} --> {entry.end}"]

    for idx, ln in enumerate(entry.lines):
        if entry.is_spoken and idx == entry.speaker_line_index:
            # 重建说话行
            parts = [f"[{entry.speaker}]"]
            if entry.action:
                parts.append(f"{{{entry.action}}}")
            if entry.face and entry.speaker:
                parts.append(f"{{Animation:{entry.face}|character={entry.speaker}}}")
            parts.extend(entry.other_tags)
            parts.append(entry.text)
            rebuilt = ""
            for p in parts:
                if p and not rebuilt.endswith("{") and not p.startswith("{") and rebuilt:
                    rebuilt += ""
                rebuilt += p
            lines.append(rebuilt)
        else:
            lines.append(ln)

    return "\n".join(lines)


# ── 语义分析 ──
def detect_emotion(text: str) -> str:
    """根据关键词检测主要情绪。"""
    for keyword, candidates in EXPRESSION_KEYWORDS.items():
        if keyword in text:
            return candidates[0]
    return "FaceReset"


def _is_false_match(text: str, keyword: str) -> bool:
    """排除常见的关键词误匹配。"""
    if keyword == "不":
        # 避免 "不会"、"不是"、"不知道" 等触发拒绝动作
        return bool(re.search(r"不[会是知道可能行对要能]", text))
    if keyword == "跑":
        # 避免 "往哪跑"、"哪里跑" 等反问触发追逐动作
        return bool(re.search(r"[哪往]哪里?跑", text))
    return False


def _match_keyword(text: str, keyword: str) -> bool:
    """支持普通字符串或正则表达式的关键词匹配。"""
    if keyword.startswith("r\"") and keyword.endswith("\""):
        pattern = keyword[2:-1]
        return re.search(pattern, text) is not None
    elif keyword.startswith("r'") and keyword.endswith("'"):
        pattern = keyword[2:-1]
        return re.search(pattern, text) is not None
    else:
        if keyword not in text:
            return False
        return not _is_false_match(text, keyword)


def detect_action(text: str, speaker: str, current_action: Optional[str]) -> Optional[str]:
    """根据关键词和角色选择动作。角色特化优先于通用映射。"""
    overrides = CHARACTER_OVERRIDES.get(speaker, {})
    action_overrides = overrides.get("actions", {})

    # 先查角色特化；如果匹配，只按特化候选判断
    override_candidates: List[str] = []
    for keyword, candidates in action_overrides.items():
        if _match_keyword(text, keyword):
            override_candidates.extend(candidates)

    if override_candidates:
        if current_action and current_action in override_candidates:
            return None
        return override_candidates[0]

    # 再查通用
    generic_candidates: List[str] = []
    for keyword, candidates in ACTION_KEYWORDS.items():
        if _match_keyword(text, keyword):
            generic_candidates.extend(candidates)

    if not generic_candidates:
        return None

    if current_action and current_action in generic_candidates:
        return None

    return generic_candidates[0]


def pick_expression(text: str, speaker: str, context: List[str], current_face: Optional[str]) -> str:
    """综合关键词、角色特化、上下文选择表情。角色特化优先于通用映射。"""
    overrides = CHARACTER_OVERRIDES.get(speaker, {})
    expr_overrides = overrides.get("expressions", {})

    # 先查角色特化
    override_candidates: List[str] = []
    for keyword, candidates in expr_overrides.items():
        if _match_keyword(text, keyword):
            override_candidates.extend(candidates)

    if override_candidates:
        if current_face and current_face in override_candidates:
            return current_face
        return override_candidates[0]

    # 再查通用
    generic_candidates: List[str] = []
    for keyword, candidates in EXPRESSION_KEYWORDS.items():
        if _match_keyword(text, keyword):
            generic_candidates.extend(candidates)

    if not generic_candidates:
        return current_face or "FaceReset"

    # 如果当前表情已经在语义候选中，保留它
    if current_face and current_face in generic_candidates:
        return current_face

    # 上下文：如果上一条是拒绝，这条是回应，倾向于坚定/得意
    if context:
        prev = context[-1]
        if any(w in prev for w in ["不", "不能", "没", "拒绝"]):
            if "我" in text or "自己" in text:
                if "FaceDetermined" in generic_candidates:
                    return "FaceDetermined"

    return generic_candidates[0]


# ── 主流程 ──
def run_catalog(story_tool: Path, episode_dir: Path) -> Set[str]:
    """调用 story_tool.py catalog 获取可用动画集合。"""
    cmd = [
        sys.executable,
        str(story_tool),
        "catalog",
        "--episode-dir",
        str(episode_dir),
        "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[performance-director] catalog failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    catalog = json.loads(result.stdout)
    animations: Set[str] = set(catalog.get("animations", []))
    return animations


def main() -> int:
    parser = argparse.ArgumentParser(description="Performance Director for Dula scripts")
    parser.add_argument("episode_dir", type=Path, help="Episode directory")
    parser.add_argument(
        "--output", "-o", type=Path, help="Output path (default: script.story.perf in episode dir)"
    )
    parser.add_argument(
        "--story-tool",
        type=Path,
        help="Path to story_tool.py",
    )
    args = parser.parse_args()

    episode_dir: Path = args.episode_dir
    story_path = episode_dir / "script.story"
    if not story_path.is_file():
        print(f"[performance-director] script.story not found: {story_path}", file=sys.stderr)
        return 1

    output_path: Path = args.output or (episode_dir / "script.story.perf")

    # 定位 story_tool.py
    if args.story_tool:
        story_tool = args.story_tool
    else:
        # 默认：从本脚本向上找到 dula-skills/story-writer/scripts/story_tool.py
        script_dir = Path(__file__).resolve().parent
        story_tool = script_dir.parent.parent / "story-writer" / "scripts" / "story_tool.py"
    if not story_tool.is_file():
        print(f"[performance-director] story_tool.py not found: {story_tool}", file=sys.stderr)
        return 1

    # 获取可用动画
    available = run_catalog(story_tool, episode_dir)
    print(f"[performance-director] {len(available)} animations available")

    # 解析剧本
    entries = parse_story(story_path)
    print(f"[performance-director] parsed {len(entries)} entries")

    # 上下文记录
    prev_texts: List[str] = []

    optimized = 0
    for entry in entries:
        if not entry.is_spoken or not entry.speaker:
            continue

        # 选择表情
        new_face = pick_expression(entry.text, entry.speaker, prev_texts, entry.face)
        if new_face in available:
            if entry.face != new_face:
                entry.face = new_face
                optimized += 1
        else:
            print(
                f"[performance-director] warning: {new_face} not registered for {entry.speaker}",
                file=sys.stderr,
            )

        # 选择动作
        new_action = detect_action(entry.text, entry.speaker, entry.action)
        if new_action and new_action in available:
            if entry.action != new_action:
                entry.action = new_action
                optimized += 1
        elif new_action:
            print(
                f"[performance-director] warning: action {new_action} not registered, skipping",
                file=sys.stderr,
            )

        prev_texts.append(entry.text)

    print(f"[performance-director] optimized {optimized} tags")

    # 输出
    output_blocks = [render_entry(e) for e in entries]
    output_path.write_text("\n\n".join(output_blocks) + "\n", encoding="utf-8")
    print(f"[performance-director] wrote {output_path}")

    # 验证
    validate_cmd = [
        sys.executable,
        str(story_tool),
        "validate",
        "--story",
        str(output_path),
        "--episode-dir",
        str(episode_dir),
    ]
    val_result = subprocess.run(validate_cmd, capture_output=True, text=True)
    print(val_result.stdout.strip())
    if val_result.returncode != 0:
        print(val_result.stderr.strip(), file=sys.stderr)
        return val_result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
