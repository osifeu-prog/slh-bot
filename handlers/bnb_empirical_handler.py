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


    @bot.message_handler(commands=["bnb_return"])
    def bnb_return(message):
        _send_bnb_return_button(
            bot,
            message,
            preset="repay_1",
            button_text="↩️ החזר לצביקה 1 BNB",
            title="↩️ BNB REPAYMENT",
            amount="1 BNB",
        )


    @bot.message_handler(commands=["bnb_return_smoke"])
    def bnb_return_smoke(message):
        _send_bnb_return_button(
            bot,
            message,
            preset="smoke",
            button_text="🧪 שלח 0.01 BNB לבדיקה",
            title="🧪 BNB RETURN SMOKE",
            amount="0.01 BNB",
        )


def _send_bnb_return_button(bot, message, preset, button_text, title, amount):
    uid = str(message.from_user.id)
    if not is_owner(uid):
        return

    public_url = os.getenv(
        "SLH_PUBLIC_URL",
        "https://slh-cloud-bot-production.up.railway.app",
    ).rstrip("/")
    url = f"{public_url}/bnb-browser-return?preset={preset}"

    try:
        from telebot import types

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                button_text,
                web_app=types.WebAppInfo(url=url),
            )
        )
        bot.reply_to(
            message,
            f"{title}\n\n"
            "מסלול חד־פעמי לבעלים בלבד.\n"
            f"• סכום נעול: {amount}\n"
            "• יעד: ארנק BNB המאומת הנוכחי של צביקה\n"
            "• רשת: BNB Smart Chain (56)\n"
            "• הארנק שלך בלבד חותם ומשדר\n"
            "• השרת אינו מחזיק מפתח ואינו משדר\n"
            "• אימות: sender + recipient + exact Wei + 15 confirmations\n"
            "• Gas בפועל יוצג לאחר האישור\n\n"
            "לחץ על הכפתור, חבר את ה־Trezor דרך MetaMask ואשר רק את העסקה שמוצגת.\n"
            "עמלת רשת משולמת ע״י הארנק השולח ומוצגת בנפרד.\n"
            "Settlement ציבורי נשאר CLOSED.",
            reply_markup=markup,
        )
    except Exception as exc:
        bot.reply_to(message, f"❌ BNB return button failed: {type(exc).__name__}")
