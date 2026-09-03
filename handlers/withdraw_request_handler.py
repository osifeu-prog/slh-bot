import json
import time
from pathlib import Path

from core.authority import is_owner, has_permission

def register(bot):
    @bot.message_handler(commands=["withdraw"])
    def withdraw_cmd(msg):
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(msg, "שימוש: /withdraw <amount_credits> <ton_wallet_address>")
            return
        try:
            amount = float(parts[1])
            if amount <= 0:
                raise ValueError
        except:
            bot.reply_to(msg, "❌ כמות לא תקינה")
            return
        uid = str(msg.from_user.id)
        address = parts[2].strip()
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        wallet = db.get("users", {}).get(uid, {}).get("wallet", {})
        if wallet.get("credits", 0) < amount:
            bot.reply_to(msg, "❌ אין מספיק credits")
            return
        requests = db.setdefault("withdrawal_requests", {})
        req_id = f"W-{int(time.time())}"
        requests[req_id] = {
            "uid": uid,
            "amount": amount,
            "address": address,
            "status": "pending",
            "created_at": time.time(),
        }
        Path("state/db.json").write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
        bot.reply_to(msg, f"✅ בקשת משיכה {req_id} נרשמה. תטופל ידנית.")

    @bot.message_handler(commands=["approve_withdraw"])
    def approve_withdraw_cmd(msg):
        uid = str(msg.from_user.id)
        if not (is_owner(uid) or has_permission(uid, "agents.manage")):
            bot.reply_to(msg, "⛔️ Admin only")
            return
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /approve_withdraw <req_id>")
            return
        req_id = parts[1]
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        req = db.get("withdrawal_requests", {}).get(req_id)
        if not req or req["status"] != "pending":
            bot.reply_to(msg, "❌ בקשה לא נמצאה או כבר טופלה")
            return
        # כאן בפועל תשלח TON/BNB, אבל כרגע סימון ידני
        req["status"] = "approved"
        db["withdrawal_requests"][req_id] = req
        Path("state/db.json").write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
        bot.reply_to(msg, f"✅ בקשה {req_id} אושרה (טיפול ידני)")
