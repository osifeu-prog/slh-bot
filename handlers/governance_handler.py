def register(bot, context=None):

    @bot.message_handler(commands=['gov_status'])
    def gov_status(message):

        bot.send_message(
            message.chat.id,
            '🏛 SLH Governance Online\n'
            'Source: state/db.json\n'
            'Status: foundation ready'
        )
