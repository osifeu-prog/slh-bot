"""Security helpers for the SLH MCP service."""

import re

from core.exec_policy import redact_secrets


_BEARER_RE = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+")


def redact(value: str) -> str:
    text = redact_secrets(str(value))
    return _BEARER_RE.sub(r"\1[REDACTED]", text)
