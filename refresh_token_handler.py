"""
Telegram token rotation control surface.

Secrets are NEVER accepted through Telegram messages and are NEVER persisted by
this handler. Rotation is performed from an authenticated operator terminal
using rotate_telegram_token.sh, which validates the candidate token before
changing Railway's canonical BOT_TOKEN secret.
"""
import os
import subprocess


def init(bot, is_admin_func=None):
    if is_admin_func is None:
        def is_admin_func(message):
            return False

    @bot.message_handler(commands=["refreshtoken"])
    def refresh_token_start(message):
        if not is_admin_func(message):
            bot.reply_to(message, "⛔ פקודה זו לאדמין בלבד")
            return

        script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rotate_telegram_token.sh")
        if not os.path.exists(script):
            bot.reply_to(message, "❌ מנגנון הרוטציה המאובטח אינו מותקן בשרת.")
            return

        bot.reply_to(
            message,
            "🔐 רוטציית Telegram מוכנה.\n"
            "מטעמי אבטחה לא שולחים token דרך Telegram.\n"
            "הרוטציה מתבצעת מהטרמינל באמצעות rotate_telegram_token.sh: "
            "אימות getMe → עדכון Railway BOT_TOKEN.\n"
            "לאחר מכן יש לבצע redeploy ולוודא polling תקין."
        )


def register(bot, context=None):
    """Standard loader registration using canonical runtime admin authority."""
    context = context or {}
    is_admin_func = context.get("is_admin")
    if not callable(is_admin_func):
        from security.permissions import is_admin as canonical_is_admin
        is_admin_func = canonical_is_admin
    init(bot, is_admin_func)
    print("🔐 refresh_token_handler loaded (terminal-only secret rotation)")
