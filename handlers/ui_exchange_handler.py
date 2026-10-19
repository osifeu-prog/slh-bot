import math
import state_manager
from datetime import datetime, timezone

from core.slh_distribution import transfer

def _now():
    return datetime.now(timezone.utc).isoformat()

def _bal(db, uid, field):
    u = db.get("users", {}).get(str(uid))
    return float(u.get("wallet", {}).get(field, 0) or 0) if u else 0.0

def _set(db, uid, field, val):
    u = db.setdefault("users", {}).setdefault(str(uid), {})
    w = u.setdefault("wallet", {})
    w[field] = float(val)

def _ledger(db, uid, before, amount, reason, meta=None):
    after = before + amount
    db.setdefault("ledger", []).append({"time": _now(), "uid": str(uid), "before": before, "amount": amount, "after": after, "reason": reason, "meta": meta or {}})

def register(bot):
    @bot.message_handler(commands=["exchange"])
    def exchange(msg):
        bot.reply_to(
            msg,
            "📊 SLH Exchange\n\n"
            "🟢 Buy SLH:\n"
            "/buy_slh <amount_slh> <max_price_in_credits>\n\n"
            "🔴 Sell SLH:\n"
            "/sell_slh <amount_slh> <price_in_credits>\n\n"
            "📖 Open orders:\n"
            "/orders\n\n"
            "📈 Trades:\n"
            "/trades\n\n"
            "❌ Cancel order:\n"
            "/cancel <order_id>"
        )

    @bot.message_handler(commands=["p2p_slh"])
    def p2p_slh(msg):
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(msg, "Usage: /p2p_slh <recipient_uid> <amount>")
            return
        try:
            recipient = str(parts[1]); amount = float(parts[2])
        except:
            bot.reply_to(msg, "Invalid parameters")
            return
        if amount <= 0 or recipient == str(msg.from_user.id):
            bot.reply_to(msg, "Invalid amount or self-transfer")
            return
        sender = str(msg.from_user.id)
        event_id = f"p2p_slh:{sender}:{msg.chat.id}:{msg.message_id}"
        try:
            result = transfer(
                sender_uid=sender,
                recipient_uid=recipient,
                amount=amount,
                event_id=event_id,
                reason="p2p:slh",
            )
            if result.get("status") == "already_completed":
                bot.reply_to(msg, f"ℹ️ Transfer already completed: {amount:g} SLH to {recipient}")
            else:
                bot.reply_to(msg, f"Sent {amount:g} SLH to {recipient}")
        except ValueError as e:
            bot.reply_to(msg, str(e))
        except Exception as e:
            bot.reply_to(msg, f"Error: {e}")

    @bot.message_handler(commands=["p2p_credits"])
    def p2p_credits(msg):
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(msg, "Usage: /p2p_credits <recipient_uid> <amount>")
            return
        try:
            recipient = str(parts[1])
            amount = float(parts[2])
        except (TypeError, ValueError, OverflowError):
            bot.reply_to(msg, "Invalid parameters")
            return
        if not math.isfinite(amount) or amount <= 0 or recipient == str(msg.from_user.id):
            bot.reply_to(msg, "Invalid amount or self-transfer")
            return
        sender = str(msg.from_user.id)
        event_id = f"p2p_credits:{sender}:{msg.chat.id}:{msg.message_id}"

        def transfer_credits(db):
            users = db.get("users")
            if not isinstance(users, dict) or sender not in users or recipient not in users:
                raise ValueError("USER_NOT_FOUND")

            ledger = db.get("ledger", [])
            if not isinstance(ledger, list):
                raise ValueError("P2P_CREDITS_LEDGER_INVALID")
            existing = [
                row for row in ledger
                if isinstance(row, dict)
                and isinstance(row.get("meta"), dict)
                and str(row["meta"].get("event_id") or "") == event_id
            ]
            if existing:
                # Exact replay is read-only and resolved before freeze policy,
                # but only when both accounting sides and their immutable
                # identities are complete and agree with the request.
                if len(existing) != 2:
                    raise ValueError("P2P_CREDITS_IDENTITY_UNKNOWN")
                debits = [row for row in existing if row.get("reason") == "p2p:credits_sent"]
                credits_rows = [row for row in existing if row.get("reason") == "p2p:credits_received"]
                if len(debits) != 1 or len(credits_rows) != 1:
                    raise ValueError("P2P_CREDITS_IDENTITY_UNKNOWN")
                debit, credit = debits[0], credits_rows[0]
                debit_meta = debit.get("meta")
                credit_meta = credit.get("meta")
                if not isinstance(debit_meta, dict) or not isinstance(credit_meta, dict):
                    raise ValueError("P2P_CREDITS_IDENTITY_UNKNOWN")

                try:
                    debit_amount = float(debit.get("amount"))
                    credit_amount = float(credit.get("amount"))
                    debit_before = float(debit.get("before"))
                    debit_after = float(debit.get("after"))
                    credit_before = float(credit.get("before"))
                    credit_after = float(credit.get("after"))
                except (TypeError, ValueError, OverflowError):
                    raise ValueError("P2P_CREDITS_IDENTITY_UNKNOWN") from None
                values = (
                    debit_amount, credit_amount, debit_before, debit_after,
                    credit_before, credit_after,
                )
                if not all(math.isfinite(value) for value in values):
                    raise ValueError("P2P_CREDITS_IDENTITY_UNKNOWN")
                if (
                    not math.isclose(debit_before + debit_amount, debit_after, rel_tol=0.0, abs_tol=1e-9)
                    or not math.isclose(credit_before + credit_amount, credit_after, rel_tol=0.0, abs_tol=1e-9)
                ):
                    raise ValueError("P2P_CREDITS_IDENTITY_UNKNOWN")

                identity_matches = (
                    str(debit.get("uid") or "") == sender
                    and str(credit.get("uid") or "") == recipient
                    and str(debit_meta.get("recipient") or "") == recipient
                    and str(credit_meta.get("sender") or "") == sender
                    and str(debit_meta.get("event_id") or "") == event_id
                    and str(credit_meta.get("event_id") or "") == event_id
                    and math.isclose(debit_amount, -amount, rel_tol=0.0, abs_tol=1e-9)
                    and math.isclose(credit_amount, amount, rel_tol=0.0, abs_tol=1e-9)
                )
                if not identity_matches:
                    raise ValueError("P2P_CREDITS_IDENTITY_CONFLICT")
                return "already_completed"

            sender_user = users.get(sender)
            if isinstance(sender_user, dict) and sender_user.get("frozen") is True:
                raise ValueError("ACCOUNT_FROZEN")
            s_bal = _bal(db, sender, "credits")
            if not math.isfinite(s_bal) or s_bal < amount:
                raise ValueError("INSUFFICIENT_CREDITS")
            r_bal = _bal(db, recipient, "credits")
            if not math.isfinite(r_bal):
                raise ValueError("INVALID_CREDITS_BALANCE")
            _set(db, sender, "credits", s_bal - amount)
            _set(db, recipient, "credits", r_bal + amount)
            meta_sent = {"recipient": recipient, "event_id": event_id}
            meta_received = {"sender": sender, "event_id": event_id}
            _ledger(db, sender, s_bal, -amount, "p2p:credits_sent", meta_sent)
            _ledger(db, recipient, r_bal, amount, "p2p:credits_received", meta_received)
            return "completed"

        try:
            result = state_manager.atomic_update(transfer_credits)
            if result == "already_completed":
                bot.reply_to(msg, f"ℹ️ Transfer already completed: {amount:g} Credits to {recipient}")
            else:
                bot.reply_to(msg, f"Sent {amount:g} Credits to {recipient}")
        except ValueError as e:
            bot.reply_to(msg, str(e))
        except Exception as e:
            bot.reply_to(msg, f"Error: {e}")
