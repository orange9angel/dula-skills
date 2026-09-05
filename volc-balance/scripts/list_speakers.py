#!/usr/bin/env python3
"""拉取火山语音 seed-tts 大模型音色列表（ListSpeakers OpenAPI, Version=2025-05-20）。

service=speech_saas_prod, region=cn-beijing, host=open.volcengineapi.com。
签名复用 volcengine SDK 的 V4 HMAC（子类化 base.Service 注册 api_info），
凭证加载复用 check_balance.py（环境变量优先，否则自动解析 dula-story/.env.cv）。

IAM 子用户除 CVFullAccess 外，还需要语音服务（speech_saas_prod）的只读权限，
实测结论见 ../SKILL.md 翻车记录节。

Usage:
  python scripts/list_speakers.py                      # 全部音色（摘要行）
  python scripts/list_speakers.py --age 老年 --gender 男  # 筛选 + 详情（含试听）
  python scripts/list_speakers.py --json               # 原始 JSON（拉全后的合并结果）

Exit codes: 0 成功 / 2 凭证缺失 / 3 权限不足 / 1 其他错误（与 check_balance.py 一致）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_balance import (  # noqa: E402
    BalanceError,
    CREDENTIAL_ERR_CODES,
    PERMISSION_ERR_CODES,
    _load_credentials,
)

DEFAULT_RESOURCE_ID = "seed-tts-2.0"
PAGE_LIMIT = 100


def _service():
    try:
        from volcengine.ApiInfo import ApiInfo
        from volcengine.Credentials import Credentials
        from volcengine.ServiceInfo import ServiceInfo
        from volcengine.base.Service import Service
    except ImportError as exc:
        raise BalanceError(
            "volcengine SDK 未安装；请装到项目 venv："
            "dula-story/.venv/Scripts/python.exe -m pip install volcengine"
        ) from exc

    class SpeechSaaSService(Service):
        def __init__(self):
            service_info = ServiceInfo(
                "open.volcengineapi.com",
                {"Accept": "application/json"},
                Credentials("", "", "speech_saas_prod", "cn-beijing"),
                10,
                30,
            )
            api_info = {
                "ListSpeakers": ApiInfo(
                    "POST", "/",
                    {"Action": "ListSpeakers", "Version": "2025-05-20"}, {}, {},
                )
            }
            super().__init__(service_info, api_info)

        def list_speakers(self, body: dict) -> dict:
            raw = self.json("ListSpeakers", {}, json.dumps(body, ensure_ascii=False))
            if raw == "":
                raise BalanceError("语音服务返回空响应，请稍后重试")
            return json.loads(raw)

    return SpeechSaaSService()


def _raise_from_error_body(code: str, message: str) -> None:
    if any(tag in code for tag in PERMISSION_ERR_CODES):
        raise BalanceError(
            f"权限不足（{code}: {message}）。\n"
            f"IAM 子用户缺语音服务读权限，去 console.volcengine.com/iam 给子用户加"
            f"语音技术相关只读策略（策略名以控制台列表为准，实测见 SKILL.md 翻车记录）。",
            exit_code=3,
        )
    if any(tag in code for tag in CREDENTIAL_ERR_CODES):
        raise BalanceError(
            f"凭证无效（{code}: {message}）。\n"
            f"请检查 dula-story/.env.cv 中 VOLC_ACCESSKEY/VOLC_SECRETKEY 是否过期或粘贴有误。"
        )
    raise BalanceError(f"语音服务返回错误（{code}: {message}）")


def fetch_all_speakers(svc, resource_id: str) -> list[dict]:
    """分页拉全指定模型的音色列表。"""
    speakers: list[dict] = []
    page = 1
    total = None
    while True:
        body = {"ResourceIDs": [resource_id], "Page": page, "Limit": PAGE_LIMIT}
        try:
            resp = svc.list_speakers(body)
        except Exception as exc:
            # SDK 的 .json() 在非 2xx 时抛 Exception(resp.text.encode())，args[0] 是 bytes
            raw_arg = exc.args[0] if exc.args else exc
            text = raw_arg.decode("utf-8", "replace") if isinstance(raw_arg, bytes) else str(raw_arg)
            try:
                err_body = json.loads(text)
                err = (err_body.get("ResponseMetadata") or {}).get("Error") or {}
                _raise_from_error_body(err.get("Code", ""), err.get("Message", ""))
            except json.JSONDecodeError:
                pass
            lower = text.lower()
            if "timed out" in lower or "timeout" in lower:
                raise BalanceError(f"网络超时，检查本机网络或稍后重试：{text[:200]}") from exc
            if "getaddrinfo" in lower or "connection" in lower:
                raise BalanceError(f"网络错误，无法连接 open.volcengineapi.com：{text[:200]}") from exc
            raise BalanceError(f"调用 ListSpeakers 失败：{text[:300]}") from exc

        meta_error = (resp.get("ResponseMetadata") or {}).get("Error")
        if meta_error:
            _raise_from_error_body(meta_error.get("Code", ""), meta_error.get("Message", ""))

        result = resp.get("Result") or {}
        total = result.get("Total")
        batch = result.get("Speakers") or []
        speakers.extend(batch)
        if not batch or (total is not None and len(speakers) >= total):
            break
        page += 1
    return speakers


def _emotions_tag(speaker: dict) -> str:
    emotions = speaker.get("Emotions") or []
    if not emotions:
        return ""
    labels = ",".join(e.get("Label", "") for e in emotions if e.get("Label"))
    return f"[多情感:{labels}]" if labels else "[多情感]"


def print_summary(speakers: list[dict]) -> None:
    for sp in speakers:
        line = (
            f"[{sp.get('Gender', '?')}/{sp.get('Age', '?')}] "
            f"{sp.get('Name', '?')} ({sp.get('VoiceType', '?')}) "
            f"{_emotions_tag(sp)} — {sp.get('Description', '')}"
        )
        print(line)
    print(f"\n共 {len(speakers)} 个音色")


def print_detail(speakers: list[dict]) -> None:
    for i, sp in enumerate(speakers, 1):
        print(f"{i}. {sp.get('Name', '?')} ({sp.get('VoiceType', '?')})")
        print(f"   性别/年龄: {sp.get('Gender', '?')}/{sp.get('Age', '?')}  {_emotions_tag(sp)}")
        print(f"   描述: {sp.get('Description', '')}")
        langs = sp.get("Languages") or []
        if langs and langs[0].get("Text"):
            print(f"   试听文本: {langs[0]['Text']}")
        if sp.get("TrialURL"):
            print(f"   试听链接: {sp['TrialURL']}")
        print()
    print(f"共 {len(speakers)} 个匹配音色")


def main() -> int:
    parser = argparse.ArgumentParser(description="拉取火山语音 seed-tts 音色列表（ListSpeakers）")
    parser.add_argument("--age", default=None, help="按年龄筛选，如 老年/中年/青年")
    parser.add_argument("--gender", default=None, help="按性别筛选，如 男/女")
    parser.add_argument("--resource-id", default=DEFAULT_RESOURCE_ID,
                        help=f"模型版本，默认 {DEFAULT_RESOURCE_ID}")
    parser.add_argument("--json", action="store_true", help="只输出原始 JSON（合并全部分页）")
    args = parser.parse_args()

    try:
        ak, sk = _load_credentials()
        svc = _service()
        svc.set_ak(ak)
        svc.set_sk(sk)
        speakers = fetch_all_speakers(svc, args.resource_id)
    except BalanceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(speakers, ensure_ascii=False, indent=2))
        return 0

    filtered = [
        sp for sp in speakers
        if (not args.age or sp.get("Age") == args.age)
        and (not args.gender or sp.get("Gender") == args.gender)
    ]
    if args.age or args.gender:
        cond = "/".join(x for x in (args.gender, args.age) if x)
        print(f"== 筛选条件: {cond}（{args.resource_id}）==\n")
        print_detail(filtered)
    else:
        print_summary(filtered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
