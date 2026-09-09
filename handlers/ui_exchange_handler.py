import state_manager
from datetime import datetime, timezone

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
        def transfer(db):
            if sender not in db.get("users", {}) or recipient not in db.get("users", {}):
                raise ValueError("USER_NOT_FOUND")
            s_bal = _bal(db, sender, "token_balance")
            if s_bal < amount:
                raise ValueError("INSUFFICIENT_SLH")
            r_bal = _bal(db, recipient, "token_balance")
            _set(db, sender, "token_balance", s_bal - amount)
            _set(db, recipient, "token_balance", r_bal + amount)
            _ledger(db, sender, s_bal, -amount, "p2p:slh_sent", {"recipient": recipient})
            _ledger(db, recipient, r_bal, amount, "p2p:slh_received", {"sender": sender})
            return True
        try:
            state_manager.atomic_update(transfer)
            bot.reply_to(msg, f"Sent {amount} SLH to {recipient}")
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
            recipient = str(parts[1]); amount = float(parts[2])
        except:
            bot.reply_to(msg, "Invalid parameters")
            return
        if amount <= 0 or recipient == str(msg.from_user.id):
            bot.reply_to(msg, "Invalid amount or self-transfer")
            return
        sender = str(msg.from_user.id)
        def transfer(db):
            if sender not in db.get("users", {}) or recipient not in db.get("users", {}):
                raise ValueError("USER_NOT_FOUND")
            s_bal = _bal(db, sender, "credits")
            if s_bal < amount:
                raise ValueError("INSUFFICIENT_CREDITS")
            r_bal = _bal(db, recipient, "credits")
            _set(db, sender, "credits", s_bal - amount)
            _set(db, recipient, "credits", r_bal + amount)
            _ledger(db, sender, s_bal, -amount, "p2p:credits_sent", {"recipient": recipient})
            _ledger(db, recipient, r_bal, amount, "p2p:credits_received", {"sender": sender})
            return True
        try:
            state_manager.atomic_update(transfer)
            bot.reply_to(msg, f"Sent {amount} Credits to {recipient}")
        except ValueError as e:
            bot.reply_to(msg, str(e))
        except Exception as e:
            bot.reply_to(msg, f"Error: {e}")
