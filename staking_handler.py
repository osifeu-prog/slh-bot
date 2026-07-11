from telebot import TeleBot


def register_staking_handlers(bot: TeleBot):

    staking_users = {}

    @bot.message_handler(commands=['stake'])
    def stake(m):

        user = m.from_user.id

        amount = staking_users.get(user, 0)

        bot.send_message(
            m.chat.id,
            f"""
🏦 SLH STAKING

Status:
{"Active" if amount else "Not active"}

Locked:
{amount} credits

Commands:

/stake_join
/staking_report
"""
        )


    @bot.message_handler(commands=['stake_join'])
    def stake_join(m):

        user = m.from_user.id

        if user not in staking_users:
            staking_users[user] = 100

            bot.send_message(
                m.chat.id,
                """
✅ Joined SLH Staking

Initial stake:
100 credits

Your rewards engine is active 🚀
"""
            )
        else:
            bot.send_message(
                m.chat.id,
                "ℹ️ Already staking"
            )


    @bot.message_handler(commands=['staking_report'])
    def staking_report(m):

        user = m.from_user.id

        amount = staking_users.get(user,0)

        reward = amount * 0.05

        bot.send_message(
            m.chat.id,
            f"""
📊 STAKING REPORT

Stake:
{amount}

Estimated reward:
{reward}

Status:
{"ACTIVE" if amount else "INACTIVE"}
"""
        )
