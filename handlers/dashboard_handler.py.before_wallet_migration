from telebot import types
import json

def register(bot):
    @bot.message_handler(commands=['dashboard'])
    def dashboard(m):
        try:
            with open('state/db.json', encoding='utf-8') as f:
                d = json.load(f)
        except:
            d = {}
        user_id = str(m.from_user.id)
        user = d.get('users', {}).get(user_id, {})
        balance = user.get('balance', 0)
        course = user.get('active_course', 'אין')
        text = f"🌟 ה-Dashboard שלך\n\n💰 יתרה: {balance} SLH\n📚 קורס פעיל: {course}\n🤖 סוכנים זמינים: 10\n🎯 משימה מומלצת: סיים שיעור 1 בביטקוין\n\nמה תרצה לעשות?"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton('📚 המשך לקורס', callback_data='continue_course'))
        markup.add(types.InlineKeyboardButton('🤖 צור סוכן חדש', callback_data='create_agent'))
        markup.add(types.InlineKeyboardButton('📊 סטטוס מערכת', callback_data='system_status'))
        bot.send_message(m.chat.id, text, reply_markup=markup, parse_mode='Markdown')
