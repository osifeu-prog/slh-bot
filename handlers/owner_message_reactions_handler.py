"""Owner-only Telegram reactions for incoming messages.

A first-position handler adds one context-sensitive reaction and returns
ContinueHandling so all existing commands and natural-chat handlers still run.
Other users, groups, and additional bots are unaffected. Set
SLH_OWNER_MESSAGE_REACTIONS=0 to disable this feature.
"""
from __future__ import annotations

import logging
import os
import re

from core.authority import is_owner
from telebot import types
from telebot.handler_backends import ContinueHandling

_LOGGER = logging.getLogger(__name__)
_FAILURE_LOGGED = False
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
_OWNER_MESSAGE_CONTENT_TYPES = [
    "text", "audio", "document", "photo", "sticker", "video", "video_note",
    "voice", "contact", "location", "venue", "animation", "dice", "game",
    "poll", "story", "web_app_data",
]


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

    # Diagnostic commands should signal that the message was noticed and will
    # be inspected. Telegram's reaction catalog is stricter than normal emoji.
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
    """Register a first-position acknowledgement handler for the primary bot."""
    context = context if isinstance(context, dict) else {}
    if str(context.get("bot_name") or "") != "Me_ad_main":
        return False

    def owner_message_reaction(message):
        global _FAILURE_LOGGED
        try:
            if reactions_enabled():
                sender = getattr(message, "from_user", None)
                if is_owner(getattr(sender, "id", None)):
                    chat = getattr(message, "chat", None)
                    if getattr(chat, "type", None) == "private":
                        chat_id = getattr(chat, "id", None)
                        message_id = getattr(message, "message_id", None)
                        if chat_id is not None and isinstance(message_id, int):
                            bot.set_message_reaction(
                                chat_id=chat_id,
                                message_id=message_id,
                                reaction=[
                                    types.ReactionTypeEmoji(
                                        emoji=choose_reaction(message)
                                    )
                                ],
                            )
        except Exception as exc:
            # Reaction failures must never block existing handlers or spam logs.
            if not _FAILURE_LOGGED:
                _LOGGER.warning(
                    "Owner message reaction unavailable (%s); message handling continues",
                    type(exc).__name__,
                )
                _FAILURE_LOGGED = True

        # Critical: preserve normal command and natural-chat processing.
        return ContinueHandling()

    bot.message_handler(
        func=lambda _message: True,
        content_types=_OWNER_MESSAGE_CONTENT_TYPES,
    )(owner_message_reaction)
    return True
