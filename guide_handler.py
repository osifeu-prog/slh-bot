from telebot import TeleBot


def init(bot: TeleBot):

    @bot.message_handler(commands=['guide'])
    def guide(message):

        text = """
📘 SLH GUIDE

ברוכים הבאים ל-SLH OS 🚀

מערכת הפעלה חכמה הכוללת:

📚 קורסים ולמידה
🤖 סוכני AI
📋 משימות ופרויקטים
💰 כלכלה דיגיטלית
🛒 Marketplace
📊 דוחות והתקדמות
🧠 AI Assistant
🩺 בדיקות מערכת

✅ הכל כבר מחובר.
אין צורך להתחיל מאפס.

פקודות התחלה:

📚 /courses
🤖 /agents
📊 /report
🩺 /doctor
📘 /help

שאל את ה-AI:
/ask <שאלה>
"""

        bot.reply_to(message, text.strip())
