from core.profile_manager import get_user
from core.stake_position import get_positions
from core.staking_service import stake_locked, unstake_locked


def register(bot):
    @bot.message_handler(commands=["stake"])
    def stake(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /stake <amount>")
            return
        try:
            amount = int(parts[1])
            uid = str(msg.from_user.id)
            user = get_user(uid) or {}
            course = user.get("academy", {}).get("courses", {}).get("bitcoin_mastery")
            if not course or course.get("stage", 0) < 3:
                bot.reply_to(msg, "יש להשלים לפחות 3 שיעורים בקורס Bitcoin לפני סטייקינג.")
                return
            result = stake_locked(uid, amount, lock_days=30, meta={"source": "telegram", "command": "stake"})
            bot.reply_to(msg, f"{amount} credits הועברו לסטייקינג\nיתרה: {result['credits']}\nסטייק: {result['staked']}\nPosition: {result['position']['id']}")
        except Exception as e:
            bot.reply_to(msg, f"{e}")

    @bot.message_handler(commands=["unstake"])
    def unstake(msg):
        bot.reply_to(
            msg,
            "הסטייקינג החדש נעול לפי Position.\n"
            "לשחרור לאחר תום התקופה השתמש ב:\n"
            "/unstake_lock <position_id>\n\n"
            "לא ניתן לעקוף את תקופת הנעילה באמצעות /unstake <amount>."
        )

    @bot.message_handler(commands=["stake_lock"])
    def stake_lock(msg):
        parts = msg.text.split()
        if len(parts) < 3:
            bot.reply_to(msg, "שימוש: /stake_lock <amount> <days>")
            return
        try:
            amount = int(parts[1])
            days = int(parts[2])
            uid = str(msg.from_user.id)
            user = get_user(uid) or {}
            course = user.get("academy", {}).get("courses", {}).get("bitcoin_mastery")
            if not course or course.get("stage", 0) < 3:
                bot.reply_to(msg, "יש להשלים לפחות 3 שיעורים בקורס Bitcoin לפני סטייקינג.")
                return
            result = stake_locked(uid, amount, lock_days=days, meta={"source": "telegram", "command": "stake_lock", "days": days})
            pos = result["position"]
            bot.reply_to(msg, f"{amount} credits הועברו לסטייקינג נעול\nתקופה: {days} ימים\nיתרה: {result['credits']}\nסטייק: {result['staked']}\nPosition: {pos['id']}")
        except Exception as e:
            bot.reply_to(msg, f"{e}")

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
        from core.reward_engine import calculate_reward
        positions = get_positions(uid)
        if not positions:
            bot.reply_to(msg, "אין פוזיציות.")
            return
        lines = ["תגמולים צפויים:"]
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
        try:
            res = unstake_locked(uid, parts[1], meta={"source": "telegram", "command": "unstake_lock"})
            if res.get("status") == "duplicate":
                bot.reply_to(msg, "הפוזיציה כבר שוחררה.")
                return
            bot.reply_to(msg, f"שוחררו {res['position']['amount']} credits.\nיתרה: {res['credits']}\nסטייק: {res['staked']}")
        except Exception as e:
            bot.reply_to(msg, f"{e}")

    @bot.message_handler(commands=["staking"])
    def staking_help(msg):
        bot.reply_to(msg, "סטייקינג SLH\n\nאיך מתחילים?\n1. רכוש credits באמצעות Stars:\n     /pay\n2. נעל credits:\n     /stake <amount>\n\nפקודות:\n/stake <amount>\n/unstake <amount> — חסום עבור סטייק נעול\n/stake_lock <amount> <days>\n/unstake_lock <position_id>\n/positions\n/rewards\n\nסטייקינג פנימי בלבד, לא on-chain.")
