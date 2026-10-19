"""Owner-only Telegram reactions for incoming messages.

Reactions are applied in middleware so existing command and conversation handlers
continue to process the original update. Other users, groups, and other bots are
not affected. Set SLH_OWNER_MESSAGE_REACTIONS=0 to disable this feature.
"""
from __future__ import annotations

import logging
import os
import re

from core.authority import is_owner

_LOGGER = logging.getLogger(__name__)
_FAILURE_LOGGED = False
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def reactions_enabled() -> bool:
    value = str(os.getenv("SLH_OWNER_MESSAGE_REACTIONS", "1") or "1").strip().lower()
    return value not in _FALSE_VALUES


def choose_reaction(message) -> str:
    """Pick one Telegram-supported reaction from bounded, local message cues."""
    text = str(
        getattr(message, "text", None)
        or getattr(message, "caption", None)
        or ""
    ).strip()
    lowered = text.lower()

    # Diagnostic commands and pasted runtime output deserve an acknowledgement
    # that signals the message was noticed and is being inspected.
    if lowered.startswith(("/e ", "/check_", "/release", "/audit", "/go_live_report")):
        return "👀"

    if any(token in lowered for token in (
        "blocked", "syntaxerror", "traceback", "exception", "failed",
        "failure", "error", "שגיאה", "נכשל", "חסום", "תקלה",
    )):
        return "🤔"

    if (
        "slh_diag_ok" in lowered
        or re.search(r"\b(pass|passed|success)\b", lowered)
        or "בדיקה הצליחה" in text
        or "הושלם" in text
    ):
        return "👍"

    if "?" in text or "؟" in text or any(
        term in text for term in ("האם", "איך", "למה", "אפשר", "מדוע")
    ):
        return "🤔"

    if lowered.startswith("/"):
        return "👌"
    return "🤝"


def register(bot, context=None):
    """Register middleware for the primary owner bot only."""
    context = context if isinstance(context, dict) else {}
    if str(context.get("bot_name") or "") != "Me_ad_main":
        return False

    try:
        from telebot import apihelper, types

        # pyTelegramBotAPI requires this global switch before middleware runs.
        apihelper.ENABLE_MIDDLEWARE = True

        def owner_message_reaction(_bot_instance, message):
            global _FAILURE_LOGGED
            if not reactions_enabled():
                return

            sender = getattr(message, "from_user", None)
            if not is_owner(getattr(sender, "id", None)):
                return

            chat = getattr(message, "chat", None)
            if getattr(chat, "type", None) != "private":
                return

            chat_id = getattr(chat, "id", None)
            message_id = getattr(message, "message_id", None)
            if chat_id is None or not isinstance(message_id, int):
                return

            try:
                bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[types.ReactionTypeEmoji(emoji=choose_reaction(message))],
                )
            except Exception as exc:
                # Reaction failures must never block existing handlers or spam logs.
                if not _FAILURE_LOGGED:
                    _LOGGER.warning(
                        "Owner message reaction unavailable (%s); message handling continues",
                        type(exc).__name__,
                    )
                    _FAILURE_LOGGED = True

        bot.middleware_handler(update_types=["message"])(owner_message_reaction)
        return True
    except Exception as exc:
        _LOGGER.warning("Unable to register owner message reaction middleware (%s)", type(exc).__name__)
        return False
