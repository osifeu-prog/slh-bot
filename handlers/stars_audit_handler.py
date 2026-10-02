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


def _is_testish(row):
    """Identify explicit local test/legacy records without guessing from amounts."""
    if not isinstance(row, dict):
        return False
    meta = row.get("meta") or {}
    if meta.get("test") is True or meta.get("is_test") is True:
        return True
    uid = str(row.get("uid") or "").strip().lower()
    reference = str(row.get("reference") or row.get("charge_id") or "").strip().lower()
    return (
        uid.startswith("test")
        or reference.startswith("test")
        or "boundary-test" in reference
        or reference.startswith("fakepay")
    )


def _local_snapshot():
    db = state_manager.load_db()
    confirmed = {}
    local_test_ids = set()

    transactions = db.get("transactions", [])
    if isinstance(transactions, list):
        for row in transactions:
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

    for charge, row in (db.get("vip_subscriptions", {}) or {}).items():
        charge = str(charge).strip()
        if not charge:
            continue
        confirmed[charge] = {
            "charge_id": charge,
            "uid": str(row.get("uid", "")),
            "stars": int(row.get("stars_paid", row.get("stars", 0)) or 0),
            "kind": "vip",
            "status": str(row.get("status", "RECORDED")),
            "testish": _is_testish(row),
        }

    for order in (db.get("star_item_orders", {}) or {}).values():
        if not isinstance(order, dict):
            continue
        charge = str(order.get("charge_id") or "").strip()
        if not charge:
            continue
        confirmed[charge] = {
            "charge_id": charge,
            "uid": str(order.get("uid", "")),
            "stars": int(order.get("stars_paid", 0) or 0),
            "kind": "store",
            "status": str(order.get("status", "RECORDED")),
            "item_id": str(order.get("item_id", "")),
            "testish": _is_testish(order),
        }
        if confirmed[charge]["testish"]:
            local_test_ids.add(charge)

    revenue = db.get("revenue_ledger", [])
    revenue_refs = set()
    test_revenue_refs = set()
    if isinstance(revenue, list):
        for row in revenue:
            if str(row.get("currency", "")).upper() != "XTR":
                continue
            reference = str(row.get("reference") or "").strip()
            if not reference:
                continue
            revenue_refs.add(reference)
            if _is_testish(row):
                test_revenue_refs.add(reference)

    return db, confirmed, revenue_refs, local_test_ids, test_revenue_refs


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
            (
                db,
                confirmed,
                revenue_refs,
                local_test_ids,
                test_revenue_refs,
            ) = _local_snapshot()

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

            matched_gross = sum(confirmed[c]["stars"] for c in matched)
            local_gross = sum(v["stars"] for v in confirmed.values())
            local_only_gross = sum(confirmed[c]["stars"] for c in local_only)
            real_local_ids = local_ids - local_test_ids
            missing_revenue_refs = sorted(real_local_ids - revenue_refs)
            orphan_revenue_refs = sorted(
                (revenue_refs - local_ids) - test_revenue_refs
            )
            test_local_only = sorted(set(local_only) & local_test_ids)

            lines = [
                "⭐ SLH — Telegram Stars authoritative audit",
                f"Bot Stars balance: {int((balance or {}).get('amount', 0) or 0)}⭐",
                f"Telegram transactions fetched: {len(transactions)}",
                f"Incoming invoice payments: {len(incoming_invoice)} / {incoming_gross}⭐ gross",
                f"Outgoing Stars transactions: {len(outgoing)} / {outgoing_total}⭐",
                f"Local payment records: {len(local_ids)} / {local_gross}⭐",
                f"Matched charge IDs: {len(matched)} / {matched_gross}⭐",
                f"Telegram-only confirmed payments: {len(telegram_only)}",
                f"Local-only records: {len(local_only)} / {local_only_gross}⭐",
                f"Local real payment refs missing from revenue_ledger: {len(missing_revenue_refs)}",
                f"XTR revenue refs missing local record: {len(orphan_revenue_refs)}",
                f"Test/legacy local-only records: {len(test_local_only)}",
                f"Test/legacy XTR revenue refs: {len(test_revenue_refs)}",
            ]

            if telegram_only:
                lines.append("
⚠️ TELEGRAM-ONLY (money received, local record not found):")
                for charge in telegram_only[:20]:
                    tx = next(x for x in incoming_invoice if str(x.get("id")) == charge)
                    lines.append("• " + _fmt_tx(tx))

            if local_only:
                lines.append("
⚠️ LOCAL-ONLY (not present in Telegram history):")
                for charge in local_only[:20]:
                    row = confirmed[charge]
                    label = "TEST/LEGACY" if charge in local_test_ids else "REAL"
                    lines.append(
                        f"• {charge} | {row['stars']}⭐ | uid={row['uid']} | "
                        f"{row['kind']} | {label}"
                    )

            if missing_revenue_refs:
                lines.append("
⚠️ LOCAL REAL PAYMENTS MISSING REVENUE LEDGER:")
                for charge in missing_revenue_refs[:20]:
                    row = confirmed[charge]
                    lines.append(
                        f"• {charge} | {row['stars']}⭐ | uid={row['uid']} | {row['kind']}"
                    )

            if orphan_revenue_refs:
                lines.append("
⚠️ REVENUE LEDGER REFS WITHOUT LOCAL PAYMENT RECORD:")
                for charge in orphan_revenue_refs[:20]:
                    lines.append(f"• {charge}")

            lines.append("
Matched payment details:")
            for tx in incoming_invoice:
                charge = str(tx.get("id") or "")
                if charge in matched:
                    local = confirmed.get(charge, {})
                    lines.append("• " + _fmt_tx(tx))
                    lines.append(
                        f"  local: uid={local.get('uid')} stars={local.get('stars')} "
                        f"kind={local.get('kind')} status={local.get('status')}"
                    )

            lines.append("
Latest Telegram invoice transactions:")
            for tx in incoming_invoice[-10:]:
                lines.append("• " + _fmt_tx(tx))

            bot.send_message(m.chat.id, "
".join(lines)[:3900])
        except Exception as exc:
            print(f"[STARS_AUDIT] read-only audit failed: {type(exc).__name__}")
            bot.send_message(
                m.chat.id,
                "❌ Stars audit failed safely. No balances or payments were changed.",
            )
