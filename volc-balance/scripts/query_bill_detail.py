#!/usr/bin/env python3
"""查询火山引擎账单明细（费用中心 OpenAPI: ListBillDetail, Version=2022-01-01）。

按账期+产品关键词过滤，用于核对某次按量付费任务（Seed-Audio/Seedance/
OmniHuman/seed-tts 等）到底扣了多少钱。账单按小时出账，刚跑完的任务可能
延迟 1~2 小时才出现。

凭证与退出码约定同 check_balance.py（自动解析 dula-story/.env.cv）。

Usage:
  python scripts/query_bill_detail.py                      # 本月全部按量明细摘要
  python scripts/query_bill_detail.py --period 2026-09 --product 语音
  python scripts/query_bill_detail.py --json               # 原始 JSON
"""
from __future__ import annotations

import argparse
import json
import sys

from check_balance import BalanceError, _load_credentials

PERMISSION_ERR_CODES = (
    "AccessDenied", "Forbidden", "Unauthorized", "AuthFailure",
    "OperationDenied", "NoPermission", "PolicyDenied",
)


def _service(ak: str, sk: str):
    try:
        from volcengine.ApiInfo import ApiInfo
        from volcengine.Credentials import Credentials
        from volcengine.ServiceInfo import ServiceInfo
        from volcengine.base.Service import Service
    except ImportError as exc:
        raise BalanceError("volcengine SDK 未安装，请先 pip install volcengine") from exc

    class BillingReadService(Service):
        def __init__(self):
            service_info = ServiceInfo(
                "billing.volcengineapi.com",
                {"Accept": "application/json"},
                Credentials(ak, sk, "billing", "cn-north-1"),
                10,
                60,
            )
            api_info = {
                "ListBillDetail": ApiInfo(
                    "GET", "/",
                    {"Action": "ListBillDetail", "Version": "2022-01-01"}, {}, {},
                )
            }
            super().__init__(service_info, api_info)

    return BillingReadService()


def query_details(ak: str, sk: str, period: str, product: str = "", limit: int = 100) -> list[dict]:
    svc = _service(ak, sk)
    items: list[dict] = []
    offset = 0
    while True:
        params = {"BillPeriod": period, "GroupTerm": "0", "GroupPeriod": "2",
                  "IgnoreZero": "0", "NeedRecordNum": "1",
                  "Limit": str(limit), "Offset": str(offset)}
        if product:
            params["Product"] = product
        try:
            raw = svc.get("ListBillDetail", params)
        except Exception as exc:
            text = exc.args[0].decode("utf-8", "replace") if exc.args and isinstance(exc.args[0], bytes) else str(exc)
            try:
                err = (json.loads(text).get("ResponseMetadata") or {}).get("Error") or {}
                code, message = err.get("Code", ""), err.get("Message", "")
            except json.JSONDecodeError:
                code, message = "", text[:200]
            if any(tag in code for tag in PERMISSION_ERR_CODES):
                raise BalanceError(
                    f"权限不足（{code}: {message}）。给子用户加 BillingCenterReadOnlyAccess 策略。",
                    exit_code=3,
                ) from exc
            raise BalanceError(f"查询账单明细失败（{code}: {message}）") from exc
        resp = json.loads(raw) if isinstance(raw, str) else raw
        result = resp.get("Result") or {}
        batch = result.get("List") or []
        items.extend(batch)
        total = result.get("TotalNum") or result.get("Total") or 0
        offset += len(batch)
        if not batch or len(batch) < limit or (total and offset >= total):
            return items


def summarize(items: list[dict]) -> None:
    by_product: dict[str, float] = {}
    for it in items:
        product = it.get("ProductZh") or it.get("Product") or "未知产品"
        amount = float(it.get("DiscountBillAmount") or it.get("PayableAmount") or 0)
        by_product[product] = by_product.get(product, 0) + amount
    print(f"共 {len(items)} 条明细，按产品汇总：")
    for product, amount in sorted(by_product.items(), key=lambda kv: -kv[1]):
        print(f"  {product}：¥{amount:.4f}")


def print_rows(items: list[dict], rows: int = 30) -> None:
    for it in items[-rows:]:
        print(json.dumps({k: it.get(k) for k in (
            "ExpenseBeginTime", "Product", "ProductZh", "BillingMode",
            "Price", "PriceUnit", "Count", "Unit",
            "OriginalBillAmount", "DiscountBillAmount", "PayableAmount",
        ) if k in it}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="查询火山引擎账单明细（ListBillDetail）")
    parser.add_argument("--period", default="", help="账期 YYYY-MM，默认当前月")
    parser.add_argument("--product", default="", help="产品过滤关键词（服务端过滤），如：语音")
    parser.add_argument("--contains", default="", help="本地再过滤：产品名包含该词，如：语音/音频/Seed")
    parser.add_argument("--json", action="store_true", help="只输出原始 JSON")
    args = parser.parse_args()

    period = args.period
    if not period:
        from datetime import date
        period = date.today().strftime("%Y-%m")

    try:
        ak, sk = _load_credentials()
        items = query_details(ak, sk, period, args.product)
    except BalanceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code

    if args.contains:
        items = [it for it in items if args.contains in json.dumps(it, ensure_ascii=False)]

    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"== 账单明细 {period} ==")
        summarize(items)
        print("\n== 最近条目 ==")
        print_rows(items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
