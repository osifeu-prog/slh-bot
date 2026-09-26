"""Canonical FAQ access for user-facing AI context.

The FAQ is documentation, not runtime state. Live runtime/account checks remain
authoritative for balances, deployment state, and other changing data.
"""
from __future__ import annotations

from pathlib import Path
import re

FAQ_PATH = Path("docs/FAQ.md")
MAX_FAQ_CHARS = 12000
MAX_CONTEXT_CHARS = 5000


def load_faq() -> str:
    try:
        text = FAQ_PATH.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    if len(text) > MAX_FAQ_CHARS:
        return text[:MAX_FAQ_CHARS] + "\n...[FAQ truncated]"
    return text


def relevant_faq(question: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Return only FAQ sections plausibly relevant to the question.

    This keeps LLM prompts small while retaining the canonical source.
    """
    text = load_faq()
    if not text:
        return ""

    q = str(question or "").strip().lower()
    sections = re.split(r"(?=^## \d+\. )", text, flags=re.MULTILINE)
    if not q:
        return text[:max_chars]

    scored = []
    for section in sections:
        if not section.strip():
            continue
        heading_match = re.match(r"^## \d+\. (.+)$", section.strip(), re.MULTILINE)
        heading = heading_match.group(1).lower() if heading_match else ""
        words = set(re.findall(r"[\wא-ת]+", q))
        score = sum(1 for word in words if len(word) >= 3 and word in section.lower())
        if any(term in q for term in ("kyc", "אימות זהות")) and "kyc" in section.lower():
            score += 5
        if any(term in q for term in ("ton", "ton connect", "ארנק", "wallet")) and "ton" in section.lower():
            score += 3
        if any(term in q for term in ("credit", "credits", "קרדיט")) and "credits" in section.lower():
            score += 3
        if score:
            scored.append((score, heading, section.strip()))

    if not scored:
        return "אין סעיף FAQ ממוקד לשאלה זו. אל תנחש; הסתמך על ה-runtime או אמור שאינך יודע."

    scored.sort(key=lambda item: (-item[0], item[1]))
    chunks = []
    used = 0
    for _, _, section in scored:
        if used + len(section) + 2 > max_chars:
            break
        chunks.append(section)
        used += len(section) + 2

    return "\n\n".join(chunks)


def faq_available() -> bool:
    return FAQ_PATH.is_file()


__all__ = ["FAQ_PATH", "load_faq", "relevant_faq", "faq_available"]
