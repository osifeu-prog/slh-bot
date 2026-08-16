from core import money_service


def register(bot):

    @bot.message_handler(commands=['stake'])
    def stake_cmd(msg):
        try:
            parts = msg.text.split()

            if len(parts) != 2:
                bot.reply_to(msg, "Usage: /stake <amount>")
                return

            amount = int(parts[1])

            if amount <= 0:
                bot.reply_to(msg, "Amount must be positive.")
                return

            uid = str(msg.from_user.id)

            result = money_service.stake(
                uid,
                amount,
                idempotency_key=f"telegram:stake:{msg.chat.id}:{msg.message_id}",
            )

            bot.reply_to(
                msg,
                f"Stake successful: {amount} credits.\n"
                f"Staked balance: {result}"
            )

        except ValueError as e:
            if str(e) == "Insufficient credits":
                bot.reply_to(msg, "Not enough credits.")
            else:
                bot.reply_to(msg, f"Stake failed: {e}")

        except Exception as e:
            print(f"[STAKE] ERROR: {e}")
            bot.reply_to(msg, "Stake failed.")


    @bot.message_handler(commands=['unstake'])
    def unstake_cmd(msg):
        try:
            parts = msg.text.split()

            if len(parts) != 2:
                bot.reply_to(msg, "Usage: /unstake <amount>")
                return

            amount = int(parts[1])

            if amount <= 0:
                bot.reply_to(msg, "Amount must be positive.")
                return

            uid = str(msg.from_user.id)

            result = money_service.unstake(
                uid,
                amount,
                idempotency_key=f"telegram:unstake:{msg.chat.id}:{msg.message_id}",
            )

            bot.reply_to(
                msg,
                f"Unstake successful: {amount} credits.\n"
                f"Available balance: {result}"
            )

        except ValueError as e:
            if str(e) == "Insufficient staked":
                bot.reply_to(msg, "Not enough staked credits.")
            else:
                bot.reply_to(msg, f"Unstake failed: {e}")

        except Exception as e:
            print(f"[UNSTAKE] ERROR: {e}")
            bot.reply_to(msg, "Unstake failed.")
