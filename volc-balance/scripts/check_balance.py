#!/usr/bin/env python3
"""查询火山引擎账户余额（费用中心 OpenAPI: QueryBalanceAcct, Version=2022-01-01）。

签名复用 volcengine SDK 的 BillingService（service=billing, region=cn-north-1,
host=billing.volcengineapi.com），仅追加 SDK 未内置的 QueryBalanceAcct api_info。

凭证：优先读环境变量 VOLC_ACCESSKEY / VOLC_SECRETKEY；没有则自动解析
dula-story/.env.cv（脚本自行解析 KEY=VALUE，不依赖 shell source）。
IAM 子用户需要费用中心读权限（Finance 相关只读策略，详见 SKILL.md）。

Usage:
  python scripts/check_balance.py          # 中文摘要 + 原始 JSON
  python scripts/check_balance.py --json   # 只打原始 JSON

Exit codes: 0 成功 / 2 凭证缺失 / 3 权限不足 / 1 其他错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AK_ENV = "VOLC_ACCESSKEY"
SK_ENV = "VOLC_SECRETKEY"

# 结果字段 -> 中文标签（值都是字符串形式的金额，单位元）
FIELD_LABELS = [
    ("AvailableBalance", "可用余额"),
    ("CashBalance", "现金余额"),
    ("FreezeAmount", "冻结金额"),
    ("ArrearsBalance", "欠费金额"),
    ("CreditLimit", "信控额度"),
]

PERMISSION_ERR_CODES = (
    "AccessDenied", "Forbidden", "Unauthorized", "AuthFailure",
    "OperationDenied", "NoPermission", "PolicyDenied",
)
CREDENTIAL_ERR_CODES = ("InvalidAccessKeyId", "SignatureDoesNotMatch", "InvalidSecretKey")


class BalanceError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


def _parse_env_file(path: Path) -> dict:
    """解析 KEY=VALUE 行（兼容 export 前缀、引号、注释），不打印任何值。"""
    pairs: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            pairs[key] = value
    return pairs


def _load_credentials() -> tuple[str, str]:
    ak = os.environ.get(AK_ENV, "")
    sk = os.environ.get(SK_ENV, "")
    if ak and sk:
        return ak, sk
    # 候选 .env.cv 位置：cwd、cwd/dula-story、工作区根/dula-story
    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parents[2]  # scripts -> volc-balance -> dula-skills -> root
    candidates = [
        Path.cwd() / ".env.cv",
        Path.cwd() / "dula-story" / ".env.cv",
        workspace_root / "dula-story" / ".env.cv",
    ]
    for path in candidates:
        if path.is_file():
            pairs = _parse_env_file(path)
            ak = ak or pairs.get(AK_ENV, "")
            sk = sk or pairs.get(SK_ENV, "")
            if ak and sk:
                return ak, sk
    raise BalanceError(
        f"凭证缺失：环境变量 {AK_ENV}/{SK_ENV} 未设置，"
        f"也未在 dula-story/.env.cv 中找到。\n"
        f"请先 source dula-story/.env.cv，或确认该文件存在且含 {AK_ENV}/{SK_ENV}。",
        exit_code=2,
    )


def _query_balance(ak: str, sk: str) -> dict:
    try:
        from volcengine.ApiInfo import ApiInfo
        from volcengine.billing.BillingService import BillingService
    except ImportError as exc:
        raise BalanceError(
            "volcengine SDK 未安装；请装到项目 venv："
            "dula-story/.venv/Scripts/python.exe -m pip install volcengine"
        ) from exc

    svc = BillingService()
    svc.set_ak(ak)
    svc.set_sk(sk)
    # SDK 未内置 QueryBalanceAcct，追加 GET api_info（Version=2022-01-01）
    svc.api_info["QueryBalanceAcct"] = ApiInfo(
        "GET", "/", {"Action": "QueryBalanceAcct", "Version": "2022-01-01"}, {}, {}
    )
    try:
        raw = svc.get("QueryBalanceAcct", {})
    except Exception as exc:
        _raise_from_sdk_error(exc)
    if raw == "":
        raise BalanceError("费用中心返回空响应，请稍后重试")
    resp = json.loads(raw)
    # SDK 只在非 2xx 时抛异常；个别错误也可能以 200 + Error 结构返回，兜底检查
    meta_error = (resp.get("ResponseMetadata") or {}).get("Error")
    if meta_error:
        _raise_from_error_body(meta_error.get("Code", ""), meta_error.get("Message", ""))
    return resp


def _raise_from_sdk_error(exc: Exception) -> None:
    """SDK 在非 2xx 时 raise Exception(resp.text)，尝试解析出结构化错误。"""
    text = str(exc)
    try:
        body = json.loads(text)
        err = (body.get("ResponseMetadata") or {}).get("Error") or body.get("Error") or {}
        _raise_from_error_body(err.get("Code", ""), err.get("Message", ""))
    except json.JSONDecodeError:
        pass
    lower = text.lower()
    if "timed out" in lower or "timeout" in lower:
        raise BalanceError(f"网络超时，检查本机网络或稍后重试：{text[:200]}") from exc
    if "name or service not known" in lower or "getaddrinfo" in lower or "connection" in lower:
        raise BalanceError(f"网络错误，无法连接 billing.volcengineapi.com：{text[:200]}") from exc
    raise BalanceError(f"调用费用中心接口失败：{text[:300]}") from exc


def _raise_from_error_body(code: str, message: str) -> None:
    if any(tag in code for tag in PERMISSION_ERR_CODES):
        raise BalanceError(
            f"权限不足（{code}: {message}）。\n"
            f"IAM 子用户缺费用中心读权限，去 console.volcengine.com/iam 给子用户加 "
            f"BillingCenterReadOnlyAccess（费用中心全部只读）策略。",
            exit_code=3,
        )
    if any(tag in code for tag in CREDENTIAL_ERR_CODES):
        raise BalanceError(
            f"凭证无效（{code}: {message}）。\n"
            f"请检查 dula-story/.env.cv 中 {AK_ENV}/{SK_ENV} 是否过期或粘贴有误。"
        )
    raise BalanceError(f"费用中心返回错误（{code}: {message}）")


def _format_summary(result: dict) -> str:
    lines = []
    account_id = result.get("AccountID")
    if account_id is not None:
        lines.append(f"账户ID：{account_id}")
    for field, label in FIELD_LABELS:
        if field in result:
            lines.append(f"{label}：¥{result[field]}")
    try:
        arrears = float(result.get("ArrearsBalance") or 0)
        if arrears > 0:
            lines.append("⚠ 存在欠费，部分按量付费服务可能已被停用，请尽快充值。")
    except (TypeError, ValueError):
        pass
    return "\n".join(lines) if lines else "(响应中没有已知余额字段，见下方原始 JSON)"


def main() -> int:
    parser = argparse.ArgumentParser(description="查询火山引擎账户余额（QueryBalanceAcct）")
    parser.add_argument("--json", action="store_true", help="只输出原始 JSON")
    args = parser.parse_args()

    try:
        ak, sk = _load_credentials()
        resp = _query_balance(ak, sk)
    except BalanceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    raw_json = json.dumps(resp, ensure_ascii=False, indent=2)
    if args.json:
        print(raw_json)
    else:
        result = resp.get("Result") or {}
        print("== 火山引擎账户余额 ==")
        print(_format_summary(result))
        print("\n== 原始 JSON ==")
        print(raw_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
