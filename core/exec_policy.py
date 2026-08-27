import json
import os
import re
import subprocess
import time

from core.identity import OWNER_TELEGRAM_ID


def is_owner(user_id) -> bool:
    return int(user_id) == int(OWNER_TELEGRAM_ID)


_LAST_EXEC = {}


def rate_limit_ok(user_id, min_interval_seconds=2):
    now = time.time()

    if user_id in _LAST_EXEC:
        if now - _LAST_EXEC[user_id] < min_interval_seconds:
            return False

    _LAST_EXEC[user_id] = now
    return True


DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\brm\s+-fr\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bchmod\s+-R\s+777\b",
    r"\bchown\s+-R\b",
    r"\bcurl\b.*\|\s*(ba)?sh\b",
    r"\bwget\b.*\|\s*(ba)?sh\b",
    r"\bpkill\s+-9\s+-f\s+bot_gateway\b",
    r"\bstate/db\.json\b",
]


def is_dangerous(cmd):
    return any(
        re.search(pattern, cmd, re.IGNORECASE)
        for pattern in DANGEROUS_PATTERNS
    )


SECRET_PATTERNS = [
    re.compile(r"\d{8,10}:AA[A-Za-z0-9_-]{33}"),
    re.compile(r"(sk-|gsk_|AIzaSy)[A-Za-z0-9_-]{20,}"),
]


def redact_secrets(text):
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)

    return text


AUDIT_PATH = "state/exec_audit.json"


def audit(user_id, cmd, source, result):
    try:
        try:
            with open(AUDIT_PATH, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []

        logs.append({
            "user": str(user_id),
            "cmd": cmd,
            "source": source,
            "result": result,
            "time": time.time()
        })

        os.makedirs(
            os.path.dirname(AUDIT_PATH),
            exist_ok=True
        )

        with open(AUDIT_PATH, "w", encoding="utf-8") as f:
            json.dump(
                logs,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception:
        pass


def run_gated(user_id, cmd, source="exec", timeout=15, max_output=4000):

    if not is_owner(user_id):
        return False, "⛔ Owner only."

    if not rate_limit_ok(user_id):
        return False, "⏳ Too fast."

    if is_dangerous(cmd):
        audit(user_id, cmd, source, "blocked")
        return False, "⛔ Command blocked."

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        output = redact_secrets(
            (result.stdout or "") +
            (result.stderr or "")
        )

        if len(output) > max_output:
            output = output[:max_output] + "\n... truncated"

        audit(
            user_id,
            cmd,
            source,
            f"exit_{result.returncode}"
        )

        return True, output or "(no output)"

    except Exception as e:
        audit(
            user_id,
            cmd,
            source,
            f"error_{type(e).__name__}"
        )

        return False, f"❌ Error: {e}"
