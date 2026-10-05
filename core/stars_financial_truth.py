"""Canonical read-only Telegram Stars financial truth for Mini App/Control Plane.

The owner view performs a live Telegram reconciliation against the local
canonical payment records. It never mutates balances, payments, or the DB.
Non-owner callers receive only their own locally recorded payment summary.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

import state_manager


def _telegram(method: str, params: dict | None = None):
    token = str(os.getenv("BOT_TOKEN", "") or "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN_UNAVAILABLE")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "TELEGRAM_API_ERROR"))
    return payload.get("result")


def _fetch_transactions(max_pages: int = 20) -> list[dict]:
    rows: list[dict] = []
    for _ in range(max_pages):
        batch = _telegram("getStarTransactions", {"offset": len(rows), "limit": 100})
        txs = list((batch or {}).get("transactions") or [])
        rows.extend(x for x in txs if isinstance(x, dict))
        if len(txs) < 100:
            break
    return rows


def _is_testish(row: dict) -> bool:
    meta = row.get("meta") or {}
    if meta.get("test") is True or meta.get("is_test") is True:
        return True
    uid = str(row.get("uid") or "").strip().lower()
    reference = str(
        row.get("reference")
        or row.get("charge_id")
        or row.get("telegram_payment_charge_id")
        or ""
    ).strip().lower()
    return (
        uid.startswith("test")
        or reference.startswith("test")
        or "boundary-test" in reference
        or reference.startswith("fakepay")
    )


def _local_records(db: dict) -> tuple[dict[str, dict], set[str], set[str], set[str]]:
    confirmed: dict[str, dict] = {}
    local_test_ids: set[str] = set()

    transactions = db.get("transactions", [])
    for row in transactions if isinstance(transactions, list) else []:
        if not isinstance(row, dict):
            continue
        charge = str(row.get("telegram_payment_charge_id") or "").strip()
        if not charge:
            continue
        item = {
            "charge_id": charge,
            "uid": str(row.get("uid", "")),
            "stars": int(row.get("stars_paid", 0) or 0),
            "kind": "credits",
            "status": "RECORDED",
            "testish": _is_testish(row),
        }
        confirmed[charge] = item
        if item["testish"]:
            local_test_ids.add(charge)

    subscriptions = db.get("vip_subscriptions", {})
    for charge, row in subscriptions.items() if isinstance(subscriptions, dict) else []:
        if not isinstance(row, dict):
            continue
        charge = str(charge).strip()
        if not charge:
            continue
        item = {
            "charge_id": charge,
            "uid": str(row.get("uid", "")),
            "stars": int(row.get("stars_paid", row.get("stars", 0)) or 0),
            "kind": "vip",
            "status": str(row.get("status", "RECORDED")),
            "testish": _is_testish(row),
        }
        confirmed[charge] = item
        if item["testish"]:
            local_test_ids.add(charge)

    orders = db.get("star_item_orders", {})
    for row in orders.values() if isinstance(orders, dict) else []:
        if not isinstance(row, dict):
            continue
        charge = str(row.get("charge_id") or "").strip()
        if not charge:
            continue
        item = {
            "charge_id": charge,
            "uid": str(row.get("uid", "")),
            "stars": int(row.get("stars_paid", 0) or 0),
            "kind": "store",
            "status": str(row.get("status", "RECORDED")),
            "item_id": str(row.get("item_id", "")),
            "testish": _is_testish(row),
        }
        confirmed[charge] = item
        if item["testish"]:
            local_test_ids.add(charge)

    revenue_refs: set[str] = set()
    test_revenue_refs: set[str] = set()
    revenue = db.get("revenue_ledger", [])
    for row in revenue if isinstance(revenue, list) else []:
        if not isinstance(row, dict) or str(row.get("currency", "")).upper() != "XTR":
            continue
        ref = str(row.get("reference") or "").strip()
        if not ref:
            continue
        revenue_refs.add(ref)
        if _is_testish(row):
            test_revenue_refs.add(ref)

    return confirmed, local_test_ids, revenue_refs, test_revenue_refs


def _record_summary(rows: list[dict]) -> dict:
    by_kind = {"store": 0, "vip": 0, "credits": 0}
    total = 0
    test_total = 0
    for row in rows:
        amount = int(row.get("stars", 0) or 0)
        total += amount
        if row.get("testish"):
            test_total += amount
        kind = str(row.get("kind") or "")
        if kind in by_kind and not row.get("testish"):
            by_kind[kind] += amount
    return {
        "records": len(rows),
        "gross": total,
        "real_gross": total - test_total,
        "test_legacy_gross": test_total,
        "by_kind": by_kind,
    }


def build_stars_financial_truth(uid: str, *, owner: bool = False) -> dict:
    uid = str(uid)
    db = state_manager.load_db()
    confirmed, local_test_ids, revenue_refs, test_revenue_refs = _local_records(db)

    personal = [v for v in confirmed.values() if str(v.get("uid")) == uid]
    personal.sort(key=lambda row: row.get("charge_id", ""))

    result = {
        "generated_at": int(time.time()),
        "scope": "owner" if owner else "personal",
        "personal": _record_summary(personal),
        "source": {
            "local": "state/db.json",
            "payments": ["transactions", "vip_subscriptions", "star_item_orders"],
            "revenue": "revenue_ledger",
            "telegram": "getMyStarBalance + getStarTransactions",
        },
    }
    if not owner:
        result["status"] = "LOCAL_PERSONAL_VIEW"
        result["personal"]["records_detail"] = [
            {
                "kind": row.get("kind"),
                "stars": row.get("stars"),
                "status": row.get("status"),
                "item_id": row.get("item_id"),
            }
            for row in personal[-20:]
        ]
        return result

    transactions = _fetch_transactions()
    incoming = []
    outgoing = []
    for tx in transactions:
        src = tx.get("source") or {}
        receiver = tx.get("receiver") or {}
        if src.get("type") == "user" and src.get("transaction_type") == "invoice_payment":
            incoming.append(tx)
        elif not src and receiver:
            outgoing.append(tx)

    incoming_ids = {str(tx.get("id")) for tx in incoming if tx.get("id")}
    local_ids = set(confirmed)
    matched = sorted(incoming_ids & local_ids)
    telegram_only = sorted(incoming_ids - local_ids)
    local_only = sorted(local_ids - incoming_ids)
    real_local_ids = local_ids - local_test_ids

    incoming_gross = sum(int(tx.get("amount", 0) or 0) for tx in incoming)
    outgoing_gross = sum(int(tx.get("amount", 0) or 0) for tx in outgoing)
    local_gross = sum(int(row.get("stars", 0) or 0) for row in confirmed.values())
    local_test_gross = sum(
        int(confirmed[c].get("stars", 0) or 0)
        for c in local_test_ids
        if c in confirmed
    )
    matched_gross = sum(int(confirmed[c].get("stars", 0) or 0) for c in matched)
    local_only_gross = sum(int(confirmed[c].get("stars", 0) or 0) for c in local_only)

    missing_revenue_refs = sorted(real_local_ids - revenue_refs)
    orphan_revenue_refs = sorted((revenue_refs - local_ids) - test_revenue_refs)

    test_revenue_gross = 0
    revenue = db.get("revenue_ledger", [])
    for row in revenue if isinstance(revenue, list) else []:
        if not isinstance(row, dict):
            continue
        if str(row.get("currency", "")).upper() != "XTR":
            continue
        ref = str(row.get("reference") or "").strip()
        if ref in test_revenue_refs:
            test_revenue_gross += int(row.get("amount", 0) or 0)

    real_by_kind = {"store": 0, "vip": 0, "credits": 0}
    for charge in matched:
        row = confirmed[charge]
        if row.get("testish"):
            continue
        kind = str(row.get("kind") or "")
        if kind in real_by_kind:
            real_by_kind[kind] += int(row.get("stars", 0) or 0)

    mismatch_count = len(telegram_only)
    mismatch_count += sum(1 for charge in local_only if charge not in local_test_ids)
    mismatch_count += len(missing_revenue_refs)
    mismatch_count += len(orphan_revenue_refs)

    reconciled = (
        len(matched) == len(incoming)
        and matched_gross == incoming_gross
        and mismatch_count == 0
    )

    balance = _telegram("getMyStarBalance") or {}
    result["status"] = "LIVE_RECONCILED" if reconciled else "LIVE_RECONCILIATION_ISSUE"
    result["owner"] = {
        "bot_stars_balance": int(balance.get("amount", 0) or 0),
        "telegram_transactions_fetched": len(transactions),
        "incoming_invoice_count": len(incoming),
        "incoming_gross": incoming_gross,
        "outgoing_count": len(outgoing),
        "outgoing_gross": outgoing_gross,
        "local_payment_records": len(local_ids),
        "local_gross": local_gross,
        "real_local_gross": local_gross - local_test_gross,
        "test_legacy_local_gross": local_test_gross,
        "matched_count": len(matched),
        "matched_gross": matched_gross,
        "telegram_only_count": len(telegram_only),
        "local_only_count": len(local_only),
        "local_only_gross": local_only_gross,
        "local_real_payment_refs_missing_revenue_ledger": len(missing_revenue_refs),
        "xtr_revenue_refs_missing_local_record": len(orphan_revenue_refs),
        "test_legacy_xtr_revenue_refs": len(test_revenue_refs),
        "test_legacy_xtr_revenue_gross": test_revenue_gross,
        "real_external_gross": incoming_gross,
        "real_by_kind": real_by_kind,
        "mismatch_count": mismatch_count,
    }
    result["owner"]["matched_charge_ids"] = matched
    result["owner"]["recent_matched"] = [
        {
            "kind": confirmed[str(tx.get("id"))].get("kind"),
            "stars": int(tx.get("amount", 0) or 0),
            "telegram_uid": ((tx.get("source") or {}).get("user") or {}).get("id"),
            "date": int(tx.get("date", 0) or 0),
            "status": confirmed[str(tx.get("id"))].get("status"),
        }
        for tx in incoming[-10:]
        if str(tx.get("id")) in confirmed
    ]
    return result
