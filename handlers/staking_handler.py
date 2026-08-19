from core import economy_service


def register(bot):
    @bot.message_handler(commands=["stake"])
    def stake(msg):
        try:
            amount = int(msg.text.split()[-1])
            uid = str(msg.from_user.id)

            result = economy_service.stake_credits(
                uid,
                amount,
                meta={"source": "telegram", "command": "stake"},
            )

            bot.reply_to(
                msg,
                f"✅ {amount} credits הועברו לסטייקינג\n"
                f"💰 יתרה: {result["credits"]}\n"
                f"🔒 סטייק: {result["staked"]}"
            )

        except ValueError as e:
            bot.reply_to(msg, f"❌ {e}")
        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")


    @bot.message_handler(commands=["unstake"])
    def unstake(msg):
        try:
            amount = int(msg.text.split()[-1])
            uid = str(msg.from_user.id)

            result = economy_service.unstake_credits(
                uid,
                amount,
                meta={"source": "telegram", "command": "unstake"},
            )

            bot.reply_to(
                msg,
                f"✅ {amount} credits הוחזרו מהסטייקינג\n"
                f"💰 יתרה: {result["credits"]}\n"
                f"🔒 סטייק: {result["staked"]}"
            )

        except ValueError as e:
            bot.reply_to(msg, f"❌ {e}")
        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")
