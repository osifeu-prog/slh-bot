"""Owner-only reactions on messages sent by the primary bot to its owner.

The wrapper observes the actual Message returned by send_message, so the
reaction targets the bot's response rather than the incoming owner message.
Reply helpers that delegate to send_message are covered too. Other users,
groups, additional bots, and normal message dispatch are unaffected.
Set SLH_OWNER_MESSAGE_REACTIONS=0 to disable this feature.
"""
from __future__ import annotations

import logging
import os
import re

from core.authority import is_owner
from telebot import types

_LOGGER = logging.getLogger(__name__)
_FAILURE_LOGGED = False
_REGISTERED_ATTRIBUTE = "_slh_owner_reply_reactions_registered"
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def reactions_enabled() -> bool:
    value = str(os.getenv("SLH_OWNER_MESSAGE_REACTIONS", "1") or "1").strip().lower()
    return value not in _FALSE_VALUES


def choose_reaction(message_or_text) -> str:
    """Pick one Telegram-supported reaction from bounded, local message cues."""
    if isinstance(message_or_text, str):
        text = message_or_text.strip()
    else:
        text = str(
            getattr(message_or_text, "text", None)
            or getattr(message_or_text, "caption", None)
            or ""
        ).strip()
    lowered = text.lower()

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
    """Wrap the primary bot's send_message to react to actual owner-directed replies."""
    context = context if isinstance(context, dict) else {}
    if str(context.get("bot_name") or "") != "Me_ad_main":
        return False

    if getattr(bot, _REGISTERED_ATTRIBUTE, False):
        return True

    original_send_message = bot.send_message

    def send_message_with_owner_reaction(*args, **kwargs):
        global _FAILURE_LOGGED

        # Never change message delivery: reaction failures are deliberately
        # contained after the underlying send succeeds.
        sent = original_send_message(*args, **kwargs)
        try:
            chat_id = kwargs.get("chat_id")
            if chat_id is None and args:
                chat_id = args[0]

            # The owner's private-chat ID is positive and passes canonical
            # owner authority. This excludes group replies and other users.
            if (
                reactions_enabled()
                and chat_id is not None
                and str(chat_id).lstrip("+").isdigit()
                and int(chat_id) > 0
                and is_owner(chat_id)
            ):
                message_id = getattr(sent, "message_id", None)
                if isinstance(message_id, int):
                    sent_chat = getattr(sent, "chat", None)
                    target_chat_id = getattr(sent_chat, "id", chat_id)
                    text = getattr(sent, "text", None)
                    if text is None:
                        text = kwargs.get("text")
                    if text is None and len(args) > 1:
                        text = args[1]
                    bot.set_message_reaction(
                        chat_id=target_chat_id,
                        message_id=message_id,
                        reaction=[
                            types.ReactionTypeEmoji(emoji=choose_reaction(text or ""))
                        ],
                    )
        except Exception as exc:
            # Reaction failure must not hide a successful reply or spam logs.
            if not _FAILURE_LOGGED:
                _LOGGER.warning(
                    "Owner reply reaction unavailable (%s); message delivery continues",
                    type(exc).__name__,
                )
                _FAILURE_LOGGED = True
        return sent

    bot.send_message = send_message_with_owner_reaction
    setattr(bot, _REGISTERED_ATTRIBUTE, True)
    return True
