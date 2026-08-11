from heb_convert import convert_to_hebrew
import re

COMMON_HEBREW = {
    "האם","אפשר","את","אני","אתה",
    "המערכת","שלום","בוט",
    "עזרה","בדיקה","תודה",
    "מה","איך","למה","של","עם","על",
    "לה","הבוט","עובד","עונה",
    "סנכרון","מערכת"
}


def looks_like_command(text):
    return text.strip().startswith("/")


def contains_url(text):
    low = text.lower()
    return (
        "http://" in low
        or "https://" in low
        or "www." in low
    )


def hebrew_ratio(text):
    if not text:
        return 0

    count = sum(
        "\u0590" <= c <= "\u05FF"
        for c in text
    )

    return count / len(text)


def hebrew_word_score(text):
    words = re.findall(r"[\u0590-\u05FF]+", text)

    if not words:
        return 0

    hits = sum(
        1 for w in words
        if w in COMMON_HEBREW
    )

    return hits / len(words)


def should_convert_keyboard(text):

    if looks_like_command(text):
        return False

    if contains_url(text):
        return False

    converted = convert_to_hebrew(text)

    if hebrew_ratio(text) > 0.1:
        return False

    if hebrew_ratio(converted) < 0.35:
        return False

    if hebrew_word_score(converted) > 0:
        return True

    return False


def normalize_keyboard_text(text):

    if should_convert_keyboard(text):
        return convert_to_hebrew(text)

    return text
