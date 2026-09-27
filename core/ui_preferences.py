"""Canonical per-user UI preferences shared by Telegram bot and Mini App.

The preferences live in state/db.json and contain no secrets.
"""
from __future__ import annotations

from copy import deepcopy

import state_manager


THEMES = {
    "calm": {
        "label": "רגוע כהה",
        "description": "כהה, נקי ונוח לעיניים",
    },
    "system": {
        "label": "לפי Telegram",
        "description": "עוקב אחרי ערכת Telegram במכשיר",
    },
    "light": {
        "label": "בהיר",
        "description": "רקע בהיר עם ניגודיות מאוזנת",
    },
    "contrast": {
        "label": "ניגודיות גבוהה",
        "description": "טקסט ופקדים בולטים יותר",
    },
}
DEFAULT_THEME = "calm"

THEME_ALIASES = {
    "dark": "calm",
    "כהה": "calm",
    "רגוע": "calm",
    "telegram": "system",
    "מערכת": "system",
    "light": "light",
    "בהיר": "light",
    "high-contrast": "contrast",
    "high_contrast": "contrast",
    "contrast": "contrast",
    "ניגודיות": "contrast",
}


def normalize_theme(value: str | None) -> str:
    key = str(value or "").strip().lower()
    key = THEME_ALIASES.get(key, key)
    return key if key in THEMES else DEFAULT_THEME


def validate_theme(value: str | None) -> str:
    key = str(value or "").strip().lower()
    key = THEME_ALIASES.get(key, key)
    if key not in THEMES:
        raise ValueError("THEME_INVALID")
    return key


def get_preferences(uid) -> dict:
    uid = str(uid)
    db = state_manager.load_db()
    raw = (db.get("ui_preferences") or {}).get(uid) or {}
    return {
        "theme": normalize_theme(raw.get("theme")),
        "language": str(raw.get("language") or "he").strip().lower()[:8] or "he",
        "compact": bool(raw.get("compact", False)),
    }


def set_preferences(uid, *, theme=None, language=None, compact=None) -> dict:
    uid = str(uid)
    current = get_preferences(uid)
    updated = dict(current)
    if theme is not None:
        updated["theme"] = validate_theme(theme)
    if language is not None:
        updated["language"] = str(language).strip().lower()[:8] or current["language"]
    if compact is not None:
        updated["compact"] = bool(compact)

    def mutate(db):
        prefs = db.setdefault("ui_preferences", {})
        prefs[uid] = deepcopy(updated)

    state_manager.atomic_update(mutate)
    return updated


def theme_choices() -> list[dict]:
    return [
        {"id": key, **value}
        for key, value in THEMES.items()
    ]
