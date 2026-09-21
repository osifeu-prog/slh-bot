"""Central Telegram token control surface.

The handler never accepts token values through Telegram. It exposes only
non-secret ownership metadata and terminal instructions for rotation.
"""

from __future__ import annotations

from pathlib import Path

from core.telegram_token_registry import get_bot, list_bots


def _script_path() -> Path:
    return Path(__file__).resolve().with_name("rotate_telegram_token.sh")


def _bot_summary(bot: dict) -> str:
    targets = bot["targets"]
    target_text = ", ".join(
        f'{t["project"]}/{t["service"]}:{t["variable"]}' for t in targets
    )
    return f'• {bot["alias"]} → @{bot["username"]} → {target_text}'


def bots_text() -> str:
    lines = ["🤖 SLH BOT CONTROL", "", "Telegram ownership map:"]
    lines.extend(_bot_summary(bot) for bot in list_bots())
    lines.extend(
        [
            "",
            "🔐 Tokens are never entered through Telegram.",
            "Use /refreshtoken <alias> to get the secure terminal rotation target.",
        ]
    )
    return "
".join(lines)


def rotation_instructions(alias: str) -> str:
    bot = get_bot(alias)
    script = _script_path()
    target_lines = "
".join(
        f'• {t["project"]}/{t["service"]} → {t["variable"]}'
        for t in bot["targets"]
    )
    return (
        f'🔐 TOKEN ROTATION — @{bot["username"]}

'
        f'{target_lines}

'
        "The token is NOT accepted in Telegram.
"
        "Run this from the operator terminal:
"
        f'{script.name} {bot["alias"]}

'
        "The script validates Telegram getMe against the expected bot identity, "
        "updates every mapped Railway target, and redeploys explicitly."
    )


def init(bot, is_admin_func=None):
    if is_admin_func is None:
        def is_admin_func(message):
            return False

    @bot.message_handler(commands=["bots", "botcontrol"])
    def bots_control(message):
        if not is_admin_func(message):
            bot.reply_to(message, "⛔ פקודה זו לאדמין בלבד")
            return
        bot.reply_to(message, bots_text())

    @bot.message_handler(commands=["refreshtoken"])
    def refresh_token_start(message):
        if not is_admin_func(message):
            bot.reply_to(message, "⛔ פקודה זו לאדמין בלבד")
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            aliases = ", ".join(item["alias"] for item in list_bots())
            bot.reply_to(
                message,
                "🔐 בחר בוט לרוטציה:
"
                "/refreshtoken <alias>

"
                f"Available: {aliases}",
            )
            return

        alias = parts[1].strip().lower()
        try:
            text = rotation_instructions(alias)
        except KeyError:
            bot.reply_to(
                message,
                "❌ Bot alias לא מוכר. השתמש ב-/bots כדי לראות את המיפוי.",
            )
            return

        if not _script_path().exists():
            bot.reply_to(
                message,
                "❌ rotate_telegram_token.sh לא נמצא בשרת. "
                "אין לבצע רוטציה דרך Telegram.",
            )
            return

        bot.reply_to(message, text)


def register(bot, context=None):
    context = context or {}
    is_admin_func = context.get("is_admin")
    if not callable(is_admin_func):
        from security.permissions import is_admin as canonical_is_admin
        is_admin_func = canonical_is_admin
    init(bot, is_admin_func)
    print("🔐 refresh_token_handler loaded (multi-bot terminal-only token rotation)")
