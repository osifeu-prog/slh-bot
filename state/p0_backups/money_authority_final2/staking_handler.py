from core import economy_service


def register(bot):
    @bot.message_handler(commands=['stake'])
    def stake_cmd(msg):
        try:
            parts = msg.text.split()

            if len(parts) < 2:
                bot.reply_to(msg, "שימוש: /stake <amount>")
                return

            amount = int(parts[-1])

            result = economy_service.stake(
                str(msg.from_user.id),
                amount,
                meta={"source": "telegram", "command": "stake"}
            )

            bot.reply_to(
                msg,
                f"✅ {amount} credits הועברו לסטייקינג\n"
                f"💰 Credits: {result['credits']}\n"
                f"🔒 Staked: {result['staked']}"
            )

        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")


    @bot.message_handler(commands=['unstake'])
    def unstake_cmd(msg):
        try:
            parts = msg.text.split()

            if len(parts) < 2:
                bot.reply_to(msg, "שימוש: /unstake <amount>")
                return

            amount = int(parts[-1])

            result = economy_service.unstake(
                str(msg.from_user.id),
                amount,
                meta={"source": "telegram", "command": "unstake"}
            )

            bot.reply_to(
                msg,
                f"✅ {amount} credits הוחזרו מהסטייקינג\n"
                f"💰 Credits: {result['credits']}\n"
                f"🔒 Staked: {result['staked']}"
            )

        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")
