import json
from datetime import datetime, timezone

STAKING_FILE = "/app/state/db.json"

def load_db():
    with open(STAKING_FILE) as f:
        return json.load(f)

def save_db(db):
    with open(STAKING_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def init(bot, is_admin):

    @bot.message_handler(commands=["stake"])
    def stake_info(m):
        db = load_db()
        uid = str(m.from_user.id)
        s = db.get("students", {}).get(uid, {}).get("staking", {})
        if not s.get("active"):
            msg = (
                "💰 *SLH Staking*\n\n"
                "תשואה חודשית: *4%*\n"
                "תקופה מינימלית: *6 חודשים*\n"
                "מטבעות: USDT / BTC / TON\n\n"
                "להצטרפות:\n"
                "/stake_join 500 USDT"
            )
        else:
            amount = s.get("amount_usd", 0)
            monthly = round(amount * s.get("monthly_rate", 0.04), 2)
            total_paid = s.get("total_paid", 0)
            msg = (
                f"📊 *הסטייקינג שלך*\n\n"
                f"סכום: *${amount}*\n"
                f"תשואה חודשית: *${monthly}*\n"
                f"שולם עד כה: *${total_paid}*\n"
                f"פעיל: ✅"
            )
        bot.reply_to(m, msg, parse_mode="Markdown")

    @bot.message_handler(commands=["stake_join"])
    def stake_join(m):
        db = load_db()
        uid = str(m.from_user.id)
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "שימוש: /stake_join <סכום> <מטבע>\nדוגמה: /stake_join 500 USDT")
            return
        try:
            amount = float(parts[1])
            currency = parts[2].upper()
        except:
            bot.reply_to(m, "סכום לא תקין.")
            return
        if amount < 100:
            bot.reply_to(m, "סכום מינימלי: $100")
            return
        students = db.setdefault("students", {})
        if uid not in students:
            students[uid] = {"name": m.from_user.first_name}
        students[uid]["staking"] = {
            "active": True,
            "amount_usd": amount,
            "currency": currency,
            "start_date": datetime.now(timezone.utc).isoformat(),
            "duration_months": 6,
            "monthly_rate": 0.04,
            "total_paid": 0
        }
        save_db(db)
        monthly = round(amount * 0.04, 2)
        msg = (
            f"✅ *הצטרפת לסטייקינג SLH!*\n\n"
            f"סכום: ${amount} {currency}\n"
            f"תשואה חודשית: ${monthly}\n"
            f"שלח /stake_confirm <TX_HASH> לאחר ההעברה"
        )
        bot.reply_to(m, msg)
        # notify admins
        for admin_id in db.get("admins", []):
            try:
                bot.send_message(admin_id, f"🔔 משקיע חדש: {m.from_user.first_name} - ${amount} {currency}")
            except:
                pass

    @bot.message_handler(commands=["stake_confirm"])
    def stake_confirm(m):
        parts = m.text.split()
        tx = parts[1] if len(parts) > 1 else "pending"
        db = load_db()
        uid = str(m.from_user.id)
        s = db.get("students", {}).get(uid, {}).get("staking", {})
        if not s.get("active"):
            bot.reply_to(m, "אין סטייקינג פעיל. שלח /stake_join קודם.")
            return
        s["tx_hash"] = tx
        s["confirmed"] = True
        save_db(db)
        bot.reply_to(m, f"✅ TX נרשם: {tx}\nהאדמין יאשר תוך 24 שעות.")


    @bot.message_handler(commands=["staking_report"])
    def staking_report(m):
        if not is_admin(m.chat.id):
            bot.reply_to(m, "⛔️ Admin only")
            return
        db = load_db()
        students = db.get("students", {})
        active = [(uid, d) for uid, d in students.items() if d.get("staking", {}).get("active")]
        total = sum(d["staking"]["amount_usd"] for _, d in active)
        monthly_out = round(sum(d["staking"]["amount_usd"] * d["staking"]["monthly_rate"] for _, d in active), 2)
        msg = f"📊 *דוח סטייקינג*\n\nמשקיעים פעילים: {len(active)}\nסה\"כ: ${total}\nתשלום חודשי: ${monthly_out}\n\n"
        for uid, d in active:
            s = d["staking"]
            msg += f"• {d.get('name','?')} — ${s['amount_usd']} {s['currency']}\n"
        bot.reply_to(m, msg)


# === PnL Reader from shared data (via bridge) ===
def get_trading_pnl():
    try:
        # אם יש shared volume או API call
        # כרגע נשתמש ב-dummy עד שנסנכרן volumes
        return {"total_pnl": 245.5, "trades_count": 12}
    except:
        return {"total_pnl": 0, "trades_count": 0}

# הוסף לפונקציית /stake
# (אפשר להוסיף ידנית או שאני אתן patch)
