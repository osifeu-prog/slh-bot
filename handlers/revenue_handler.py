"""Admin revenue reporting from the canonical external-payment ledger.

Internal Credit spending and test/fake payment records are intentionally excluded.
"""

import json
from pathlib import Path

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
