"""Canonical SLH AI trust wrapper.

Keeps the legacy cooldown guard and adds the Trust Layer without making the AI
an execution authority.
"""

from core.ask_guard import allow_request, guarded_message as cooldown_message
from core.trust_layer import scan

CRITICAL_SENSITIVE = {"private_key", "jwt", "github_token", "telegram_bot_token", "bearer_token", "aws_access_key", "api_key_assignment", "credential_targeting"}


def guard(text, uid=None):
    if not allow_request(text, uid):
        return False, cooldown_message()

    result = scan(text)
    if any(item in CRITICAL_SENSITIVE for item in result["indicators"]):
        return False, "🛡️ לא ניתן לעבד סודות או פרטי גישה. אל תשלח Seed Phrase, Private Key, API Key, JWT או קוד 2FA."

    return True
