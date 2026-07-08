"""
refresh_token_handler.py
תהליך בטוח להחלפת BOT_TOKEN דרך טלגרם.
הטוקן החדש נמחק מהצ'אט מיד עם קבלתו. הטוקן הישן אינו מוקלד מחדש.
"""
import json
import os
import requests

# מצב תהליך לכל אדמין (in-memory, לא נשמר בדיסק)
_pending = {}  # {user_id: "awaiting_confirm" | "awaiting_token"}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _save_config(cfg):
    backup_path = CONFIG_PATH + f".bak_refresh_{__import__('time').strftime('%Y%m%d_%H%M%S')}"
    with open(backup_path, "w") as f:
        json.dump(_load_config(), f, indent=2, ensure_ascii=False)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def _validate_token(token):
    """בודק תקינות טוקן מול Telegram API בלי להחליף כלום."""
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        data = r.json()
        if data.get("ok"):
            return True, data["result"].get("username", "unknown")
        return False, data.get("description", "unknown error")
    except Exception as e:
        return False, str(e)


def init(bot, is_admin_func=None):
    if is_admin_func is None:
        def is_admin_func(message):
            return False

    @bot.message_handler(commands=["refreshtoken"])
    def refresh_token_start(message):
        if not is_admin_func(message):
            bot.reply_to(message, "⛔ פקודה זו לאדמין בלבד")
            return
        _pending[message.from_user.id] = "awaiting_confirm"
        bot.reply_to(
            message,
            "🔐 תהליך רענון טוקן.\n"
            "פעולה זו תחליף את הטוקן הפעיל בכל המערכת (טרמוקס + Railway).\n"
            "שלח 'כן' לאישור, או 'ביטול' לעצירה."
        )

    @bot.message_handler(func=lambda m: _pending.get(m.from_user.id) == "awaiting_confirm")
    def refresh_token_confirm(message):
        uid = message.from_user.id
        text = message.text.strip()
        if text == "כן":
            _pending[uid] = "awaiting_token"
            bot.reply_to(
                message,
                "שלח עכשיו את הטוקן החדש (מ-BotFather).\n"
                "⚠️ ההודעה תימחק אוטומטית מיד אחרי הקבלה."
            )
        else:
            _pending.pop(uid, None)
            bot.reply_to(message, "❌ תהליך רענון הטוקן בוטל")

    @bot.message_handler(func=lambda m: _pending.get(m.from_user.id) == "awaiting_token")
    def refresh_token_apply(message):
        uid = message.from_user.id
        new_token = message.text.strip()
        _pending.pop(uid, None)

        # מחיקה מיידית של ההודעה עם הטוקן, בכל מצב
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass  # ייתכן שאין הרשאת מחיקה בצ'אט הזה; ממשיכים בכל מקרה

        status_msg = bot.send_message(message.chat.id, "🔍 בודק תקינות טוקן חדש...")

        valid, info = _validate_token(new_token)
        if not valid:
            bot.edit_message_text(
                f"❌ הטוקן לא תקין: {info}\nהטוקן הנוכחי נשאר ללא שינוי.",
                message.chat.id, status_msg.message_id
            )
            return

        # שלב זה עדיין לא מפעיל restart בפועל - רק כותב לconfig.json
        cfg = _load_config()
        cfg["BOT_TOKEN"] = new_token
        _save_config(cfg)

        bot.edit_message_text(
            f"✅ טוקן חדש אומת (@{info}) ונשמר ב-config.json.\n"
            "⚠️ שלב ידני נדרש עדיין: עדכון Railway ו-restart.\n"
            "הפעל בטרמוקס: railway variables set BOT_TOKEN=<חדש> && railway redeploy",
            message.chat.id, status_msg.message_id
        )
