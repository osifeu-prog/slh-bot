"""Admin revenue reporting from the canonical external-payment ledger.

Internal Credit spending and test/fake payment records are intentionally excluded.
"""

import json
from pathlib import Path

from core import revenue_ledger
from core.revenue_ledger import summary as revenue_summary


def _canonical_xtr_rows(db):
    rows = db.get("revenue_ledger", [])
    if not isinstance(rows, list):
        return []
    return [
        row for row in rows
        if isinstance(row, dict)
        and str(row.get("currency", "")) == "XTR"
        and float(row.get("amount", 0) or 0) > 0
        and str(row.get("reference", "")).strip()
    ]


def _label(row):
    source = str(row.get("source", ""))
    meta = row.get("meta") or {}
    kind = str(meta.get("kind", ""))

    if source == "telegram_stars_subscription" or kind == "vip_monthly":
        return "VIP"
    if source == "telegram_stars_item" or kind == "telegram_stars_item":
        return f"Store:{meta.get('item_id', 'item')}"
    if source == "telegram_stars":
        return "Credits"
    return source or "Other"



def reconcile_existing_commerce(db):
    """Backfill missing canonical revenue events without changing commerce state."""
    added = []

    transactions = db.get("transactions", [])
    if isinstance(transactions, list):
        for tx in transactions:
            charge_id = str(tx.get("telegram_payment_charge_id", "")).strip()
            if not charge_id or charge_id.startswith("fakepay:") or charge_id.startswith("test"):
                continue
            if str(tx.get("currency", "")) != "XTR":
                continue
            try:
                stars = int(tx.get("stars_paid", 0))
            except (TypeError, ValueError):
                continue
            if stars <= 0:
                continue
            result = revenue_ledger.record(
                source="telegram_stars",
                amount=stars,
                currency="XTR",
                reference=charge_id,
                uid=str(tx.get("uid", "")),
                meta={"kind": "telegram_stars_gross", "reconciled": True},
            )
            if result.get("status") == "recorded":
                added.append(charge_id)

    vip = db.get("vip_subscriptions", {})
    if isinstance(vip, dict):
        for charge_id, row in vip.items():
            if not isinstance(row, dict):
                continue
            try:
                stars = int(row.get("stars_paid", 0))
            except (TypeError, ValueError):
                continue
            if stars <= 0:
                continue
            result = revenue_ledger.record(
                source="telegram_stars_subscription",
                amount=stars,
                currency="XTR",
                reference=str(charge_id),
                uid=str(row.get("uid", "")),
                meta={"kind": "vip_monthly", "reconciled": True},
            )
            if result.get("status") == "recorded":
                added.append(str(charge_id))

    orders = db.get("star_item_orders", {})
    if isinstance(orders, dict):
        for row in orders.values():
            if not isinstance(row, dict) or row.get("status") != "FULFILLED":
                continue
            charge_id = str(row.get("charge_id", "")).strip()
            if not charge_id:
                continue
            try:
                stars = int(row.get("stars_paid", 0))
            except (TypeError, ValueError):
                continue
            if stars <= 0:
                continue
            result = revenue_ledger.record(
                source="telegram_stars_item",
                amount=stars,
                currency="XTR",
                reference=charge_id,
                uid=str(row.get("uid", "")),
                meta={"kind": "telegram_stars_item", "item_id": str(row.get("item_id", "")), "reconciled": True},
            )
            if result.get("status") == "recorded":
                added.append(charge_id)

    return added


def register(bot):
    @bot.message_handler(commands=["revenue"])
    def revenue_cmd(msg):
        from admin_utils import is_admin
        if not is_admin(msg):
            bot.reply_to(msg, "⛔️ Admin only")
            return

        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        rows = _canonical_xtr_rows(db)

        total_stars = sum(float(row.get("amount", 0) or 0) for row in rows)
        paying_customers = len({
            str(row.get("uid"))
            for row in rows
            if row.get("uid") not in (None, "")
        })

        by_product = {}
        for row in rows:
            label = _label(row)
            bucket = by_product.setdefault(label, {"orders": 0, "stars": 0})
            bucket["orders"] += 1
            bucket["stars"] += float(row.get("amount", 0) or 0)

        lines = [
            "📊 SLH Revenue — canonical external payments",
            f"💰 Real Telegram Stars: {total_stars:g}",
            f"👥 Paying customers: {paying_customers}",
            f"🧾 Confirmed revenue events: {len(rows)}",
        ]

        for label, bucket in sorted(by_product.items()):
            lines.append(
                f"• {label}: {bucket['stars']:g}⭐ / {bucket['orders']} payment(s)"
            )

        lines.append("")
        lines.append("ℹ️ Internal Credit spending is not cash revenue.")
        lines.append("ℹ️ Fake/test payment records are excluded because this view uses revenue_ledger.")

        bot.reply_to(msg, "\n".join(lines))


    @bot.message_handler(commands=["revenue_reconcile"])
    def revenue_reconcile_cmd(msg):
        from admin_utils import is_admin
        if not is_admin(msg):
            bot.reply_to(msg, "⛔️ Admin only")
            return
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        added = reconcile_existing_commerce(db)
        bot.reply_to(
            msg,
            "🔄 Revenue reconciliation complete.\\n"
            f"🧾 New canonical revenue events: {len(added)}\\n"
            "💰 Balances/orders/subscriptions were not changed."
        )

    @bot.message_handler(commands=["revenue_audit"])
    def revenue_audit_cmd(msg):
        from admin_utils import is_admin
        if not is_admin(msg):
            bot.reply_to(msg, "⛔️ Admin only")
            return
        data = revenue_summary()
        lines = [f"📈 Revenue ledger events: {data['events']}"]
        for currency, total in sorted(data["totals"].items()):
            lines.append(f"• {currency}: {total:g}")
        lines.append("Internal Credit spending is not counted as cash revenue.")
        bot.reply_to(msg, "\n".join(lines))
