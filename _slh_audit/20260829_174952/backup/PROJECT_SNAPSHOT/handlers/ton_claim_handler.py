
def audit_ton_claim(uid, tx_hash, amount_ton, credits):
    import json, time
    log = json.load(open("state/ton_audit.json"))
    log.append({
        "uid": uid,
        "tx_hash": tx_hash,
        "amount_ton": amount_ton,
        "credits": credits,
        "time": time.time()
    })
    open("state/ton_audit.json","w").write(json.dumps(log,indent=2))

import json
import time
from pathlib import Path
from core.ton_lab import verify_ton_deposit
from core import economy_service

def register(bot):
    @bot.message_handler(commands=["claim_ton"])
    def claim_ton_cmd(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /claim_ton <tx_hash>")
            return
        tx_hash = parts[1]
        uid = str(msg.from_user.id)
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        claimed = db.setdefault("claimed_ton_deposits", {})
        if tx_hash in claimed:
            bot.reply_to(msg, "❌ הטרנזקציה כבר נזקפה בעבר.")
            return
        res = verify_ton_deposit(tx_hash)
        if not res.get("ok"):
            bot.reply_to(msg, f"❌ ההפקדה לא אומתה: {res}")
            return
        amount_ton = res["amount_ton"]
        credits = int(amount_ton * db.get('ton_settings', {}).get('rate', 1000))
        if credits <= 0:
            bot.reply_to(msg, "❌ סכום הפקדה לא תקין.")
            return
        try:
            result = economy_service.record_transaction(
                uid,
                credits,
                reason="claim:ton_deposit",
                meta={"tx_hash": tx_hash},
            )
            claimed[tx_hash] = {
                "uid": uid,
                "amount_ton": amount_ton,
                "credits": credits,
                "claimed_at": time.time(),
            }
            Path("state/db.json").write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
            bot.reply_to(msg, f"✅ נזקפו {credits} credits\n💰 יתרה: {result.get('after', result)}\n📝 TX: {tx_hash}")
        except Exception as e:
            bot.reply_to(msg, f"❌ שגיאה בזיכוי: {e}")
