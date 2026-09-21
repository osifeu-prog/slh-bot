"""Read-only Telegram Stars reconciliation for OWNER/ADMIN."""

import json
import time
import urllib.parse
import urllib.request

import state_manager
from admin_utils import is_admin


def _telegram(bot, method, params=None):
    token = getattr(bot, "token", None) or getattr(bot, "TOKEN", None)
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


def _fetch_transactions(bot, max_pages=20):
    rows = []
    for page in range(max_pages):
        batch = _telegram(bot, "getStarTransactions", {"offset": len(rows), "limit": 100})
        txs = list((batch or {}).get("transactions") or [])
        rows.extend(txs)
        if len(txs) < 100:
            break
    return rows


def _local_snapshot():
    db = state_manager.load_db()
    confirmed = {}
    for row in db.get("transactions", []) if isinstance(db.get("transactions"), list) else []:
        charge = str(row.get("telegram_payment_charge_id") or "").strip()
        if charge:
            confirmed[charge] = {
                "charge_id": charge,
                "uid": str(row.get("uid", "")),
                "stars": int(row.get("stars_paid", 0) or 0),
                "kind": "credits",
            }

    for charge, row in (db.get("vip_subscriptions", {}) or {}).items():
        charge = str(charge).strip()
        if charge:
            confirmed.setdefault(charge, {
                "charge_id": charge,
                "uid": str(row.get("uid", "")),
                "stars": int(row.get("stars_paid", 0) or 0),
                "kind": "vip",
            })

    revenue = db.get("revenue_ledger", [])
    revenue_refs = {
        str(row.get("reference")).strip()
        for row in revenue if isinstance(revenue, list) and row.get("currency") == "XTR"
    }

    return db, confirmed, revenue_refs


def _fmt_tx(tx):
    src = tx.get("source") or {}
    receiver = tx.get("receiver") or {}
    partner = src if src else receiver
    partner_type = partner.get("type", "?")
    transaction_type = partner.get("transaction_type", "")
    user = partner.get("user") or {}
    user_id = user.get("id")
    who = f" | telegram_uid={user_id}" if user_id is not None else ""
    return (
        f"{tx.get('id','?')} | {int(tx.get('amount',0) or 0)}⭐ | "
        f"{time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(int(tx.get('date',0) or 0)))} | "
        f"{partner_type}:{transaction_type}{who}"
    )


def register(bot):
    @bot.message_handler(commands=["stars_audit"])
    def stars_audit(m):
        if not is_admin(m):
            return

        try:
            balance = _telegram(bot, "getMyStarBalance")
            transactions = _fetch_transactions(bot)
            db, confirmed, revenue_refs = _local_snapshot()

            incoming_invoice = []
            outgoing = []
            for tx in transactions:
                src = tx.get("source") or {}
                receiver = tx.get("receiver") or {}
                if src:
                    if src.get("type") == "user" and src.get("transaction_type") == "invoice_payment":
                        incoming_invoice.append(tx)
                elif receiver:
                    outgoing.append(tx)

            incoming_gross = sum(int(x.get("amount", 0) or 0) for x in incoming_invoice)
            outgoing_total = sum(int(x.get("amount", 0) or 0) for x in outgoing)
            telegram_ids = {str(x.get("id")) for x in incoming_invoice if x.get("id")}
            local_ids = set(confirmed)
            matched = sorted(telegram_ids & local_ids)
            telegram_only = sorted(telegram_ids - local_ids)
            local_only = sorted(local_ids - telegram_ids)

            local_gross = sum(v["stars"] for v in confirmed.values())
            missing_revenue_refs = sorted(local_ids - revenue_refs)

            lines = [
                "⭐ SLH — Telegram Stars authoritative audit",
                f"Bot Stars balance: {int((balance or {}).get('amount', 0) or 0)}⭐",
                f"Telegram transactions fetched: {len(transactions)}",
                f"Incoming invoice payments: {len(incoming_invoice)} / {incoming_gross}⭐ gross",
                f"Outgoing Stars transactions: {len(outgoing)} / {outgoing_total}⭐",
                f"Local confirmed charge IDs: {len(local_ids)} / {local_gross}⭐",
                f"Matched charge IDs: {len(matched)}",
                f"Telegram-only confirmed payments: {len(telegram_only)}",
                f"Local-only charge IDs: {len(local_only)}",
                f"Local XTR revenue refs missing from revenue_ledger: {len(missing_revenue_refs)}",
            ]

            if telegram_only:
                lines.append("\n⚠️ TELEGRAM-ONLY (money received, local fulfillment not found):")
                for charge in telegram_only[:20]:
                    tx = next(x for x in incoming_invoice if str(x.get("id")) == charge)
                    lines.append("• " + _fmt_tx(tx))

            if local_only:
                lines.append("\n⚠️ LOCAL-ONLY (local record, Telegram history not in fetched window):")
                for charge in local_only[:20]:
                    row = confirmed[charge]
                    lines.append(f"• {charge} | {row['stars']}⭐ | uid={row['uid']} | {row['kind']}")

            lines.append("\nMatched payment details:")
            for tx in incoming_invoice:
                charge = str(tx.get("id") or "")
                if charge in matched:
                    local = confirmed.get(charge, {})
                    lines.append("• " + _fmt_tx(tx))
                    lines.append(
                        f"  local: uid={local.get('uid')} stars={local.get('stars')} kind={local.get('kind')}"
                    )

            lines.append("\nLatest Telegram invoice transactions:")
            for tx in incoming_invoice[-10:]:
                lines.append("• " + _fmt_tx(tx))

            bot.send_message(m.chat.id, "\n".join(lines)[:3900])
        except Exception as exc:
            print(f"[STARS_AUDIT] read-only audit failed: {type(exc).__name__}")
            bot.send_message(m.chat.id, "❌ Stars audit failed safely. No balances or payments were changed.")
