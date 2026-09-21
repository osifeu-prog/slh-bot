"""Read-only reconciliation of locally confirmed Stars payments vs revenue ledger."""

from __future__ import annotations


_REVENUE_SOURCES = {
    "telegram_stars": "telegram_stars",
    "telegram_stars_item": "telegram_stars_item",
    "telegram_stars_subscription": "telegram_stars_subscription",
}


def _add_expected(rows, *, source, reference, uid, amount, reason):
    reference = str(reference or "").strip()
    if not reference:
        return
    rows.append({
        "source": source,
        "reference": reference,
        "uid": str(uid) if uid is not None else None,
        "amount": float(amount or 0),
        "currency": "XTR",
        "reason": reason,
    })


def expected_stars_payments(db: dict) -> list[dict]:
    rows = []
    for tx in db.get("transactions", []) if isinstance(db.get("transactions"), list) else []:
        if not isinstance(tx, dict):
            continue
        if str(tx.get("currency")) != "XTR":
            continue
        reference = tx.get("telegram_payment_charge_id")
        if reference:
            _add_expected(
                rows,
                source="telegram_stars",
                reference=reference,
                uid=tx.get("uid"),
                amount=tx.get("stars_paid", 0),
                reason="CREDITS_PAYMENT",
            )

    subscriptions = db.get("vip_subscriptions", {})
    if isinstance(subscriptions, dict):
        for reference, row in subscriptions.items():
            if not isinstance(row, dict):
                continue
            _add_expected(
                rows,
                source="telegram_stars_subscription",
                reference=reference,
                uid=row.get("uid"),
                amount=row.get("stars_paid", 0),
                reason="VIP_SUBSCRIPTION",
            )

    orders = db.get("star_item_orders", {})
    if isinstance(orders, dict):
        for row in orders.values():
            if not isinstance(row, dict):
                continue
            status = str(row.get("status", ""))
            if status not in {"PAID", "RECOVERABLE", "FULFILLED"}:
                continue
            _add_expected(
                rows,
                source="telegram_stars_item",
                reference=row.get("charge_id"),
                uid=row.get("uid"),
                amount=row.get("stars_paid", 0),
                reason="FULFILLMENT_RECOVERABLE" if status == "RECOVERABLE" else "STORE_ITEM_PAYMENT",
            )
    return rows


def audit(db: dict) -> dict:
    if not isinstance(db, dict):
        raise ValueError("INVALID_DB")

    recorded = set()
    for row in db.get("revenue_ledger", []) if isinstance(db.get("revenue_ledger"), list) else []:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source", ""))
        if source in _REVENUE_SOURCES and row.get("reference"):
            recorded.add((source, str(row["reference"])))

    expected = expected_stars_payments(db)
    missing = []
    covered = []
    seen = set()
    for item in expected:
        key = (item["source"], item["reference"])
        if key in seen:
            continue
        seen.add(key)
        item = dict(item)
        if key in recorded:
            item["status"] = "covered"
            covered.append(item)
        else:
            item["status"] = "missing_revenue_ledger"
            missing.append(item)

    gross_expected = sum(item["amount"] for item in expected if item["reference"])
    gross_missing = sum(item["amount"] for item in missing)
    return {
        "status": "OK" if not missing else "ATTENTION",
        "currency": "XTR",
        "definition": "confirmed Stars gross payment references vs local revenue observability ledger; not cash settlement",
        "expected_count": len(seen),
        "covered_count": len(covered),
        "missing_count": len(missing),
        "expected_gross_stars": gross_expected,
        "missing_gross_stars": gross_missing,
        "missing_revenue": missing,
    }
