from aiogram import types


def register(bot, context=None):

    @bot.message_handler(commands=['gov_status'])
    async def gov_status(message):

        await message.answer(
            '🏛 SLH Governance Online\n'
            'Source: state/db.json\n'
            'Status: foundation ready'
        )
