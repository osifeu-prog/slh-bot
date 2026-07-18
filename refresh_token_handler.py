"""
refresh_token_handler.py
תהליך בטוח להחלפת BOT_TOKEN דרך טלגרם.
דורש אימות הטוקן הנוכחי לפני קבלת החדש - מונע טעויות/בלבול.
הטוקן החדש נמחק מהצ'אט מיד עם קבלתו. הטוקן הישן אינו מוקלד מחדש.
"""
import json
import os
import requests

# מצב תהליך לכל אדמין (in-memory, לא נשמר בדיסק)
_pending = {}  # {user_id: "awaiting_confirm" | "awaiting_current" | "awaiting_token"}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _load_config():
    # Prefer config.json, fallback to environment
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)

    return {
        "BOT_TOKEN": os.getenv("BOT_TOKEN", "")
    }


def _save_config(cfg):
    import subprocess

    backup_path = CONFIG_PATH + f".bak_refresh_{__import__('time').strftime('%Y%m%d_%H%M%S')}"

    try:
        with open(backup_path, "w") as f:
            json.dump(_load_config(), f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    token = cfg.get("BOT_TOKEN", "")

    if token:
        try:
            subprocess.run(
                [
                    "railway",
                    "variables",
                    "--set",
                    f"BOT_TOKEN={token}"
                ],
                check=True,
                timeout=30,
                capture_output=True,
                text=True
            )
            return True, "railway_updated"
        except Exception as e:
            return False, str(e)

    return False, "missing_token"


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
            _pending[uid] = "awaiting_current"
            bot.reply_to(
                message,
                "🔑 שלב 1/2: שלח את הטוקן הנוכחי (הישן) לאימות.\n"
                "זה מוודא ששני הצדדים מסכימים על מה שמוחלף.\n"
                "⚠️ ההודעה תימחק אוטומטית מיד אחרי הקבלה."
            )
        else:
            _pending.pop(uid, None)
            bot.reply_to(message, "❌ תהליך רענון הטוקן בוטל")

    @bot.message_handler(func=lambda m: _pending.get(m.from_user.id) == "awaiting_current")
    def refresh_token_verify_current(message):
        uid = message.from_user.id
        claimed_current = message.text.strip()

        if claimed_current in ["ביטול", "בטל", "/cancel"]:
            _pending.pop(uid, None)
            bot.reply_to(message, "❌ תהליך רענון הטוקן בוטל")
            return


        cfg = _load_config()
        actual_current = cfg.get("BOT_TOKEN", "")

        if claimed_current != actual_current:
            _pending.pop(uid, None)
            bot.send_message(
                message.chat.id,
                "❌ הטוקן שהזנת לא תואם לטוקן הפעיל כרגע במערכת.\n"
                "תהליך רענון הטוקן בוטל, למען הזהירות."
            )
            return

        _pending[uid] = "awaiting_token"
        bot.send_message(
            message.chat.id,
            "✅ הטוקן הנוכחי אומת בהצלחה.\n"
            "🔑 שלב 2/2: שלח עכשיו את הטוקן החדש (מ-BotFather).\n"
            "⚠️ ההודעה תימחק אוטומטית מיד אחרי הקבלה."
        )

    @bot.message_handler(func=lambda m: _pending.get(m.from_user.id) == "awaiting_token")
    def refresh_token_apply(message):
        uid = message.from_user.id
        new_token = message.text.strip()
        _pending.pop(uid, None)

        status_msg = bot.send_message(message.chat.id, "🔍 בודק תקינות טוקן חדש...")

        valid, info = _validate_token(new_token)
        if not valid:
            bot.edit_message_text(
                f"❌ הטוקן לא תקין: {info}\nהטוקן הנוכחי נשאר ללא שינוי.",
                message.chat.id, status_msg.message_id
            )
            return

        cfg = _load_config()
        # גיבוי הטוקן הישן למקרה של תקלה
        old_token = cfg.get("BOT_TOKEN", "")
        if old_token and old_token != new_token:
            try:
                with open(CONFIG_PATH + ".token_backup", 'w') as bk:
                    bk.write(old_token)
                print("[TOKEN] Old token backed up")
            except Exception as e:
                print(f"[TOKEN] Backup failed: {e}")
        cfg["BOT_TOKEN"] = new_token
        _save_config(cfg)

        bot.edit_message_text(
            f"✅ טוקן חדש אומת (@{info}) ונשמר ב-config.json (בתוך container Railway).\n"
            "⚠️ שלב ידני נדרש עדיין: עדכון Railway ו-restart, וגם עדכון local config.json/state/.env בטרמוקס.\n"
            "הפעל בטרמוקס: railway variables --set BOT_TOKEN=<חדש> && railway redeploy",
            message.chat.id, status_msg.message_id
        )
