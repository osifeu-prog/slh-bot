from core import economy_service
from core.profile_manager import get_user


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
