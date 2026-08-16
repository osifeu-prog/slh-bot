import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

MESSAGE_STORE = {}

def repeat_callback(bot, call):
    original_text = MESSAGE_STORE.get(call.message.message_id)
    if original_text:
        msg = bot.send_message(call.message.chat.id, original_text)
        add_repeat_button(bot, msg, original_text)

def add_repeat_button(bot, message, text):
    MESSAGE_STORE[message.message_id] = text
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔁 Repeat", callback_data="repeat"))
    bot.edit_message_reply_markup(
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup
    )

def wrap_send_message(bot, original_send):
    def new_send(*args, **kwargs):
        msg = original_send(*args, **kwargs)
        if msg and msg.text:
            add_repeat_button(bot, msg, msg.text)
        return msg
    return new_send

def register_repeat_handler(bot):
    # bot.send_message wrapper disabled - parse mode recovery
    # bot.reply_to wrapper disabled - breaks parse_mode handling
    @bot.callback_query_handler(func=lambda call: call.data == "repeat")
    def callback(call):
        repeat_callback(bot, call)
