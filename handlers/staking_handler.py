from core import economy_service
from core.profile_manager import get_user
from core.stake_position import create_position, get_positions


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
            if not course or course.get("stage", 0) < 1:
                bot.reply_to(msg, "❌ קודם סיים את קורס Bitcoin.")
                return

            result = economy_service.stake_credits(
                uid,
                amount,
                meta={"source": "telegram", "command": "stake"},
            )

            bot.reply_to(
                msg,
                f"✅ {amount} credits הועברו לסטייקינג\n"
                f"💰 יתרה: {result['credits']}\n"
                f"🔒 סטייק: {result['staked']}"
            )

        except ValueError as e:
            bot.reply_to(msg, f"❌ {e}")
        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")


    @bot.message_handler(commands=["unstake"])
    def unstake(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /stake <amount>")
            return
        try:
            amount = int(parts[1])
            uid = str(msg.from_user.id)

            user = get_user(uid) or {}
            course = user.get("academy", {}).get("courses", {}).get("bitcoin_mastery")
            if not course or course.get("stage", 0) < 1:
                bot.reply_to(msg, "❌ קודם סיים את קורס Bitcoin.")
                return

            result = economy_service.unstake_credits(
                uid,
                amount,
                meta={"source": "telegram", "command": "unstake"},
            )

            bot.reply_to(
                msg,
                f"✅ {amount} credits הוחזרו מהסטייקינג\n"
                f"💰 יתרה: {result['credits']}\n"
                f"🔒 סטייק: {result['staked']}"
            )

        except ValueError as e:
            bot.reply_to(msg, f"❌ {e}")
        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")

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
            if not course or course.get("stage", 0) < 1:
                bot.reply_to(msg, "❌ קודם סיים את קורס Bitcoin.")
                return

            result = economy_service.stake_credits(
                uid,
                amount,
                meta={"source": "telegram", "command": "stake_lock", "days": days},
            )

            pos = create_position(uid, amount, days)

            bot.reply_to(
                msg,
                f"✅ {amount} credits הועברו לסטייקינג נעול\n"
                f"🔒 תקופה: {days} ימים\n"
                f"💰 יתרה: {result['credits']}\n"
                f"🔒 סטייק: {result['staked']}\n"
                f"🆔 Position: {pos['id']}"
            )

        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")


    @bot.message_handler(commands=["positions"])
    def positions_cmd(msg):
        uid = str(msg.from_user.id)
        positions = get_positions(uid)
        if not positions:
            bot.reply_to(msg, "אין לך פוזיציות פתוחות.")
            return
        lines = ["📌 הפוזיציות שלך:"]
        for pid, pos in positions.items():
            lines.append(
                f"• {pos['amount']} credits | {pos['lock_days']} days | {pos['status']}"
            )
        bot.reply_to(msg, "\n".join(lines))
