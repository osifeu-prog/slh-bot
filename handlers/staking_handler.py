from core.profile_manager import get_user
from core.stake_position import get_positions, get_position
from core import staking_service


COURSE_GUIDE = (
    "יש להשלים לפחות 3 שיעורים בקורס Bitcoin לפני סטייקינג.\n\n"
    "אין צורך לחפש Dashboard נפרד. המסלול הוא:\n"
    "1. /courses\n"
    "2. /course_bitcoin_mastery\n"
    "3. /lesson bitcoin_mastery 1\n"
    "4. בסיום: /finish bitcoin_mastery 1\n"
    "5. חזור על /lesson ו-/finish עבור שיעורים 2 ו-3.\n"
    "6. בדיקה: /academy_progress\n\n"
    "לאחר Stage 3 אפשר לחזור ל-/stake <amount>."
)


def register(bot):
    @bot.message_handler(commands=["stake"])
    def stake(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /stake <amount>\n\n" + COURSE_GUIDE)
            return
        try:
            amount = int(parts[1])
            uid = str(msg.from_user.id)

            user = get_user(uid) or {}
            course = user.get("academy", {}).get("courses", {}).get("bitcoin_mastery")
            if not course or course.get("stage", 0) < 3:
                bot.reply_to(msg, COURSE_GUIDE)
                return

            result = staking_service.stake_locked(
                uid,
                amount,
                lock_days=30,
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
            bot.reply_to(msg, f"{e}")
        except Exception as e:
            bot.reply_to(msg, f"{e}")

    @bot.message_handler(commands=["unstake"])
    def unstake(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(
                msg,
                "שימוש: /unstake <position_id>\n"
                "השחרור מתבצע רק לאחר תום תקופת הנעילה.\n"
                "בדיקת פוזיציות: /positions"
            )
            return

        uid = str(msg.from_user.id)
        pos_id = parts[1]
        pos = get_position(pos_id)
        if not pos or str(pos.get("uid")) != uid:
            bot.reply_to(msg, "הפוזיציה לא נמצאה או לא שייכת לך.")
            return

        try:
            res = staking_service.unstake_locked(
                uid,
                pos_id,
                meta={"source": "telegram", "command": "unstake"},
            )
            if res.get("status") == "duplicate":
                bot.reply_to(msg, "הפוזיציה כבר שוחררה.")
                return
            bot.reply_to(
                msg,
                f"שוחררו {pos.get('amount')} credits.\n"
                f"יתרה: {res.get('credits')}\n"
                f"סטייק: {res.get('staked')}"
            )
        except Exception as e:
            bot.reply_to(msg, f"{e}")

    @bot.message_handler(commands=["stake_lock"])
    def stake_lock(msg):
        parts = msg.text.split()
        if len(parts) < 3:
            bot.reply_to(msg, "שימוש: /stake_lock <amount> <days>\n\n" + COURSE_GUIDE)
            return
        try:
            amount = int(parts[1])
            days = int(parts[2])
            uid = str(msg.from_user.id)

            user = get_user(uid) or {}
            course = user.get("academy", {}).get("courses", {}).get("bitcoin_mastery")
            if not course or course.get("stage", 0) < 3:
                bot.reply_to(msg, COURSE_GUIDE)
                return

            result = staking_service.stake_locked(
                uid,
                amount,
                lock_days=days,
                meta={"source": "telegram", "command": "stake_lock"},
            )

            bot.reply_to(
                msg,
                f"{amount} credits הועברו לסטייקינג נעול\n"
                f"תקופה: {days} ימים\n"
                f"יתרה: {result['credits']}\n"
                f"סטייק: {result['staked']}\n"
                f"Position: {result['position']['id']}"
            )

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
            lines.append(
                f"{pos['amount']} credits | {pos['lock_days']} days | {pos['status']}"
            )
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
        for pid, pos in positions.items():
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
            res = staking_service.unstake_locked(
                uid,
                pos_id,
                meta={"source": "telegram", "command": "unstake_lock"},
            )
            if res.get("status") == "duplicate":
                bot.reply_to(msg, "הפוזיציה כבר שוחררה.")
                return
            bot.reply_to(
                msg,
                f"שוחררו {pos.get('amount')} credits.\n"
                f"יתרה: {res.get('credits')}\n"
                f"סטייק: {res.get('staked')}"
            )
        except Exception as e:
            bot.reply_to(msg, f"{e}")

    @bot.message_handler(commands=["staking"])
    def staking_help(msg):
        bot.reply_to(
            msg,
            "סטייקינג SLH\n\n"
            + COURSE_GUIDE
            + "\n\nפקודות:\n"
            "/stake <amount> - נעילה ל-30 יום\n"
            "/stake_lock <amount> <days> - נעילה לתקופה\n"
            "/unstake <position_id> - שחרור לאחר תום הנעילה\n"
            "/unstake_lock <position_id> - alias לשחרור\n"
            "/positions - הפוזיציות שלך\n"
            "/rewards - תגמולים\n\n"
            "סטייקינג פנימי בלבד, לא on-chain."
        )
