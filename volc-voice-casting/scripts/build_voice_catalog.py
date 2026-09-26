#!/usr/bin/env python3
"""构建 seed-tts-2.0 音色目录（voice_catalog.json），供角色选声复用。

复用 volc-balance/scripts/list_speakers.py 的 _service/fetch_all_speakers 与
check_balance.py 的 _load_credentials（凭证：环境变量优先，否则解析 dula-story/.env.cv）。
按 Name+Description 关键词给每个音色打 category 标签（演绎型/资讯型/其他）。

Usage:
  python build_voice_catalog.py                        # 拉全 + 落盘 + 打印演绎型男声摘要
  python build_voice_catalog.py --gender 女 --category 资讯
  python build_voice_catalog.py --json                 # 打印落盘的原始目录 JSON

Exit codes: 0 成功 / 2 凭证缺失 / 3 权限不足 / 1 其他错误（沿用 volc-balance 约定）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 复用 volc-balance 的 ListSpeakers 打通成果，不复制代码
SCRIPT_DIR = Path(__file__).resolve().parent
VOLC_BALANCE_SCRIPTS = SCRIPT_DIR.parents[1] / "volc-balance" / "scripts"
sys.path.insert(0, str(VOLC_BALANCE_SCRIPTS))

from check_balance import BalanceError, _load_credentials  # noqa: E402
from list_speakers import DEFAULT_RESOURCE_ID, _service, fetch_all_speakers  # noqa: E402

CATALOG_PATH = SCRIPT_DIR.parent / "references" / "voice_catalog.json"

# 分类关键词表（命中 Name 或 Description 即归类；演绎优先于资讯）
CATEGORY_KEYWORDS = {
    "演绎": ["有声书", "广播剧", "影视", "角色", "解说", "对话", "故事", "演播", "戏"],
    "资讯": ["资讯", "新闻", "播报", "通用"],
}
CATEGORY_OTHER = "其他"


def categorize(speaker: dict) -> str:
    text = f"{speaker.get('Name', '')} {speaker.get('Description', '')}"
    for category in ("演绎", "资讯"):  # 顺序即优先级
        if any(kw in text for kw in CATEGORY_KEYWORDS[category]):
            return category
    return CATEGORY_OTHER


def build_catalog(resource_id: str) -> dict:
    ak, sk = _load_credentials()
    svc = _service()
    svc.set_ak(ak)
    svc.set_sk(sk)
    speakers = fetch_all_speakers(svc, resource_id)
    for sp in speakers:
        sp["category"] = categorize(sp)
    counts: dict[str, int] = {}
    for sp in speakers:
        counts[sp["category"]] = counts.get(sp["category"], 0) + 1
    now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    return {
        "fetched_at": now,
        "resource_id": resource_id,
        "total": len(speakers),
        "category_counts": counts,
        "speakers": speakers,
    }


def _emotions_tag(speaker: dict) -> str:
    emotions = speaker.get("Emotions") or []
    labels = ",".join(e.get("Label", "") for e in emotions if e.get("Label"))
    return f"[多情感:{labels}]" if labels else ""


def print_table(speakers: list[dict]) -> None:
    for sp in speakers:
        line = (
            f"{sp.get('VoiceType', '?'):42s} "
            f"{sp.get('Name', '?'):12s} "
            f"{sp.get('Gender', '?')}/{sp.get('Age', '?')} "
            f"{_emotions_tag(sp)} — {sp.get('Description', '')}"
        )
        print(line)
    print(f"\n共 {len(speakers)} 个匹配音色")


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 seed-tts 音色目录（ListSpeakers 拉全 + 分类落盘）")
    parser.add_argument("--gender", default=None, help="按性别筛选打印，如 男/女")
    parser.add_argument("--category", default=None, choices=["演绎", "资讯", "其他"],
                        help="按分类筛选打印")
    parser.add_argument("--resource-id", default=DEFAULT_RESOURCE_ID,
                        help=f"模型版本，默认 {DEFAULT_RESOURCE_ID}")
    parser.add_argument("--json", action="store_true", help="只打印落盘的原始目录 JSON")
    args = parser.parse_args()

    try:
        catalog = build_catalog(args.resource_id)
    except BalanceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.json:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        return 0

    counts = catalog["category_counts"]
    print(f"已落盘 {CATALOG_PATH}")
    print(
        f"共 {catalog['total']} 个音色："
        + "，".join(f"{k}型 {v}" for k, v in sorted(counts.items()))
        + "\n"
    )

    gender = args.gender or "男"
    category = args.category or "演绎"
    filtered = [
        sp for sp in catalog["speakers"]
        if sp.get("Gender") == gender and sp.get("category") == category
    ]
    print(f"== {category}型{gender}声（{len(filtered)} 个）==\n")
    print_table(filtered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
