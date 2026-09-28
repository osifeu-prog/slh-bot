"""SLH Trust Layer v1.

Local, privacy-preserving classification for untrusted text. This module is
deliberately separate from execution authority: it can advise/block, but it
cannot authorize money movement, wallet signing, secrets access, or tool use.
"""

import hashlib
import re
from typing import Any

SECRET_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I)),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_-]{20,}\b")),
    ("telegram_bot_token", re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.I)),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("api_key_assignment", re.compile(
        r"\b(?:api[_ -]?key|secret|client[_ -]?secret|access[_ -]?token|auth[_ -]?token)\s*[:=]\s*['\"]?[A-Za-z0-9._~+\-/=]{12,}",
        re.I,
    )),
)

SECRET_LANGUAGE = (
    "seed phrase", "recovery phrase", "mnemonic phrase", "private key",
    "מפתח פרטי", "מילות שחזור", "ביטוי שחזור",
    "קוד 2fa", "otp code", "one-time password",
)

PROMPT_INJECTION = (
    "ignore previous instructions", "ignore all previous",
    "disregard previous", "system prompt", "developer message",
    "reveal hidden instructions", "show the hidden prompt",
    "disable safety", "bypass safety",
    "חשוף את הפרומפט", "התעלם מהוראות קודמות", "בטל את כללי הבטיחות",
)

EXTERNAL_CONTROL = (
    "railway variables set", "git push --force", "curl | sh",
    "wget | sh", "disable auth", "turn off verification",
)

CREDENTIAL_TARGETING = (
    "send me your seed", "send your private key", "share your otp",
    "give me your 2fa", "export your secret",
    "שלח לי את המפתח הפרטי", "שלח לי את מילות השחזור",
)


def fingerprint(text: Any, uid: Any = None) -> str:
    return hashlib.sha256(
        (str(text or "").strip().lower() + ":" + str(uid)).encode("utf-8")
    ).hexdigest()


def scan(text: Any) -> dict[str, Any]:
    value = str(text or "")
    lowered = value.lower()
    indicators: list[str] = []

    for name, pattern in SECRET_PATTERNS:
        if pattern.search(value):
            indicators.append(name)

    if any(phrase in lowered for phrase in SECRET_LANGUAGE):
        indicators.append("credential_language")

    if any(phrase in lowered for phrase in PROMPT_INJECTION):
        indicators.append("prompt_injection")

    if any(phrase in lowered for phrase in EXTERNAL_CONTROL):
        indicators.append("external_control_request")

    credential_targeting = any(phrase in lowered for phrase in CREDENTIAL_TARGETING)
    if credential_targeting:
        indicators.append("credential_targeting")
        indicators.append("credential_request_or_disclosure")

    indicators = list(dict.fromkeys(indicators))
    high = {
        "private_key", "jwt", "github_token", "telegram_bot_token",
        "bearer_token", "aws_access_key", "api_key_assignment",
        "credential_targeting",
    }

    if any(item in high for item in indicators):
        level = "high"
        action = "block_sensitive_action"
    elif indicators:
        level = "medium"
        action = "treat_as_untrusted_content"
    else:
        level = "low"
        action = "allow"

    return {
        "risk_level": level,
        "recommended_action": action,
        "indicators": indicators,
        "content_stored": False,
        "content_returned": False,
    }


def safe_summary(text: Any, uid: Any = None) -> dict[str, Any]:
    """Return only a classification plus a stable non-reversible request id."""
    result = scan(text)
    result["request_fingerprint"] = fingerprint(text, uid)
    return result
