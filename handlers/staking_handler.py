from core.stake_position import get_positions, get_position
from core import staking_service


ACADEMY_NOTE = (
    "Academy נשאר פעיל ונפרד מ-Staking. "
    "אין צורך להשלים קורס כדי לבצע Staking.\n\n"
    "Staking הוא מנגנון פנימי של Credits ואינו נכס on-chain."
)


def register(bot):
    @bot.message_handler(commands=["stake"])
    def stake(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /stake <amount>\n\n" + ACADEMY_NOTE)
            return
        try:
            amount = int(parts[1])
            uid = str(msg.from_user.id)
            result = staking_service.stake_locked(
                uid, amount, lock_days=30,
                meta={"source": "telegram", "command": "stake"},
            )
            bot.reply_to(
                msg,
                f"{amount} credits הועברו לסטייקינג\n"
                f"יתרה: {result['credits']}\n"
                f"סטייק: {result['staked']}\n"
                f"Position: {result['position']['id']}"
            )
        except ValueError as e:
            bot.reply_to(msg, str(e))
        except Exception as e:
            bot.reply_to(msg, str(e))

    @bot.message_handler(commands=["unstake"])
    def unstake(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /unstake <position_id>\nהשחרור מתבצע רק לאחר תום תקופת הנעילה.\nבדיקת פוזיציות: /positions")
            return
        uid = str(msg.from_user.id)
        pos_id = parts[1]
        pos = get_position(pos_id)
        if not pos or str(pos.get("uid")) != uid:
            bot.reply_to(msg, "הפוזיציה לא נמצאה או לא שייכת לך.")
            return
        try:
            res = staking_service.unstake_locked(uid, pos_id, meta={"source": "telegram", "command": "unstake"})
            if res.get("status") == "duplicate":
                bot.reply_to(msg, "הפוזיציה כבר שוחררה.")
                return
            bot.reply_to(msg, f"שוחררו {pos.get('amount')} credits.\nיתרה: {res.get('credits')}\nסטייק: {res.get('staked')}")
        except Exception as e:
            bot.reply_to(msg, str(e))

    @bot.message_handler(commands=["stake_lock"])
    def stake_lock(msg):
        parts = msg.text.split()
        if len(parts) < 3:
            bot.reply_to(msg, "שימוש: /stake_lock <amount> <days>\n\n" + ACADEMY_NOTE)
            return
        try:
            amount = int(parts[1])
            days = int(parts[2])
            uid = str(msg.from_user.id)
            result = staking_service.stake_locked(uid, amount, lock_days=days, meta={"source": "telegram", "command": "stake_lock"})
            bot.reply_to(msg, f"{amount} credits הועברו לסטייקינג נעול\nתקופה: {days} ימים\nיתרה: {result['credits']}\nסטייק: {result['staked']}\nPosition: {result['position']['id']}")
        except Exception as e:
            bot.reply_to(msg, str(e))

    @bot.message_handler(commands=["positions"])
    def positions_cmd(msg):
        uid = str(msg.from_user.id)
        positions = get_positions(uid)
        if not positions:
            bot.reply_to(msg, "אין לך פוזיציות פתוחות.")
            return
        lines = ["הפוזיציות שלך:"]
        for pid, pos in positions.items():
            lines.append(f"{pos['amount']} credits | {pos['lock_days']} days | {pos['status']}")
        bot.reply_to(msg, "\n".join(lines))

    @bot.message_handler(commands=["rewards"])
    def rewards_cmd(msg):
        uid = str(msg.from_user.id)
        from core.reward_engine import calculate_reward, claim_reward, accrue
        positions = get_positions(uid)
        if not positions:
            bot.reply_to(msg, "אין פוזיציות.")
            return
        parts = msg.text.split()
        if len(parts) >= 3 and parts[1].lower() == "claim":
            pos_id = parts[2]
            pos = get_position(pos_id)
            if not pos or str(pos.get("uid")) != uid:
                bot.reply_to(msg, "הפוזיציה לא נמצאה או לא שייכת לך.")
                return
            try:
                accrued = accrue(pos_id)
                if accrued.get("status") == "closed":
                    bot.reply_to(msg, "הפוזיציה כבר נסגרה.")
                    return
                result = claim_reward(pos_id)
                if result.get("status") in {"already_paid", "duplicate", "nothing_to_claim"}:
                    bot.reply_to(msg, "אין כרגע תגמול חדש למימוש.")
                    return
                bot.reply_to(msg, f"תגמול שולם: {result.get('amount', 0)} credits\nיתרה: {result.get('after', 'עודכנה')}")
            except Exception as e:
                bot.reply_to(msg, str(e))
            return
        lines = ["תגמולים צפויים:", "למימוש: /rewards claim <position_id>"]
        for pid in positions:
            try:
                r = calculate_reward(pid)
            except Exception:
                r = 0
            lines.append(f"{pid}: {r} credits")
        bot.reply_to(msg, "\n".join(lines))

    @bot.message_handler(commands=["unstake_lock"])
    def unstake_lock_cmd(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /unstake_lock <position_id>")
            return
        uid = str(msg.from_user.id)
        pos_id = parts[1]
        pos = get_position(pos_id)
        if not pos or str(pos.get("uid")) != uid:
            bot.reply_to(msg, "הפוזיציה לא נמצאה או לא שייכת לך.")
            return
        try:
            res = staking_service.unstake_locked(uid, pos_id, meta={"source": "telegram", "command": "unstake_lock"})
            if res.get("status") == "duplicate":
                bot.reply_to(msg, "הפוזיציה כבר שוחררה.")
                return
            bot.reply_to(msg, f"שוחררו {pos.get('amount')} credits.\nיתרה: {res.get('credits')}\nסטייק: {res.get('staked')}")
        except Exception as e:
            bot.reply_to(msg, str(e))

    @bot.message_handler(commands=["staking"])
    def staking_help(msg):
        bot.reply_to(msg, "סטייקינג SLH\n\n" + ACADEMY_NOTE + "\n\nפקודות:\n" "/stake <amount> - נעילה ל-30 יום\n" "/stake_lock <amount> <days> - נעילה לתקופה\n" "/unstake <position_id> - שחרור לאחר תום הנעילה\n" "/unstake_lock <position_id> - alias לשחרור\n" "/positions - הפוזיציות שלך\n" "/rewards - תגמולים\n" "/rewards claim <position_id> - מימוש תגמול חדש\n\n" "Academy נשאר פעיל כמסלול למידה נפרד.")
