"""Canonical FAQ loader for user-facing AI context.

The FAQ is documentation, not runtime state. Live runtime/account checks remain
authoritative for balances, deployment state, and other changing data.
"""
from pathlib import Path

FAQ_PATH = Path("docs/FAQ.md")
MAX_FAQ_CHARS = 12000


def load_faq() -> str:
    try:
        text = FAQ_PATH.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    if len(text) > MAX_FAQ_CHARS:
        return text[:MAX_FAQ_CHARS] + "\n...[FAQ truncated]"
    return text


def faq_available() -> bool:
    return FAQ_PATH.is_file()


__all__ = ["FAQ_PATH", "load_faq", "faq_available"]
