import time
import telebot

# חשוב: תייבא את הבוט שלך כרגיל מקובץ קיים
# לדוגמה:
# from bot_fix import bot

def start_safe_polling(bot):
    print("🚀 SAFE POLLING STARTED")

    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=10,
                long_polling_timeout=10,
                none_stop=True,
                interval=0
            )

        except Exception as e:
            print("⚠️ polling error:", repr(e))
            time.sleep(3)

# הפעלה (אם אתה מריץ ישירות)
if __name__ == "__main__":
    from bot_fix import bot
    start_safe_polling(bot)
