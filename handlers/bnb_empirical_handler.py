"""Owner-only temporary Telegram entrypoint for the BNB empirical smoke.

The bot does not sign or broadcast transactions. It opens a Telegram Mini App
that uses the user's wallet provider for the single 0.01 BNB canary transfer.
"""
import os

from core.authority import is_owner


def register(bot):
    @bot.message_handler(commands=["bnb_smoke", "bnbtest"])
    def bnb_smoke(message):
        uid = str(message.from_user.id)
        if not is_owner(uid):
            return

        public_url = os.getenv(
            "SLH_PUBLIC_URL",
            "https://slh-cloud-bot-production.up.railway.app",
        ).rstrip("/")
        url = public_url + "/bnb-smoke"

        try:
            from telebot import types

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "⚡️ שלח 0.01 BNB לבדיקה",
                    web_app=types.WebAppInfo(url=url),
                )
            )
            bot.reply_to(
                message,
                "🧪 BNB EMPIRICAL SMOKE\n\n"
                "בדיקה חד־פעמית לבעלים בלבד.\n"
                "• סכום: 0.01 BNB\n"
                "• רשת: BNB Smart Chain (56)\n"
                "• Settlement ציבורי: CLOSED\n"
                "• הארנק שלך בלבד מאשר את העסקה\n"
                "• השרת לא מחזיק מפתח ולא חותם\n\n"
                "לחץ על הכפתור. לאחר אישור הארנק המערכת תמתין ל־15 confirmations "
                "ותבצע settlement idempotent של +10 Credits.",
                reply_markup=markup,
            )
        except Exception as exc:
            bot.reply_to(message, f"❌ BNB smoke button failed: {type(exc).__name__}")
