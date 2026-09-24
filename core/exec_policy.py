import json
import os
import re
import subprocess
import time

from core.authority import is_owner as authority_is_owner, has_permission


def is_owner(user_id) -> bool:
    return authority_is_owner(user_id)


def is_admin(user_id) -> bool:
    return has_permission(user_id, "exec.audit")


_LAST_EXEC = {}


def rate_limit_ok(user_id, min_interval_seconds=2):
    now = time.time()
    if user_id in _LAST_EXEC:
        if now - _LAST_EXEC[user_id] < min_interval_seconds:
            return False
    _LAST_EXEC[user_id] = now
    return True


DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b", r"\brm\s+-fr\b", r"\bmkfs\b", r"\bdd\s+if=",
    r"\bshutdown\b", r"\breboot\b", r"\bchmod\s+-R\s+777\b", r"\bchown\s+-R\b",
    r"\bcurl\b.*\|\s*(ba)?sh\b", r"\bwget\b.*\|\s*(ba)?sh\b",
    r"\bpkill\s+-9\s+-f\s+bot_gateway\b", r"\b>\s*state/db\.json\b",
    r">>?\s*state[/\\]", r"open\(\s*f?[\"'][^\"']*state[/\\][^\"']*[\"']\s*,\s*[\"'][waxc]",
    r"(?=.*state[/\\])(?=.*\.write_text\()", r"(?=.*state[/\\])(?=.*\.write_bytes\()",
    r"(?=.*state[/\\])(?=.*\bjson\.dump\()", r"\brm\s+.*state[/\\]",
    r"\bmv\s+.*state[/\\]", r"\bshutil\.(move|copy|rmtree)\(.*state[/\\]",
    # Raw wallet token balances may only be mutated by canonical application authorities.
    r"""(?:\[\s*["']token_balance["']\s*\]|\.token_balance\s*)\+?\s*=""",
    r"""\.update\(\s*\{[^}]*["']token_balance["']""",
    r"""\.setdefault\(\s*["']token_balance["']""",
]


def is_dangerous(cmd):
    return any(re.search(p, cmd, re.IGNORECASE) for p in DANGEROUS_PATTERNS)


# Audit commands are deliberately read-only. This is narrower than arbitrary
# shell execution and is available only to ADMIN/DEVELOPER/OWNER identities.
AUDIT_COMMAND_PATTERNS = [
    r"^whoami\s*$",
    r"^pwd\s*$",
    r"^grep\s+",
    r"^grep\s+-",
    r"^find\s+",
    r"^head(?:\s+-n)?\s+",
    r"^tail(?:\s+-n)?\s+",
    r"^cat\s+",
    r"^sed\s+-n\s+",
    r"^awk\s+",
]


def is_audit_command(cmd):
    if any(re.search(p, cmd, re.IGNORECASE) for p in AUDIT_COMMAND_PATTERNS):
        # No command chaining, redirection, command substitution or writes.
        if re.search(r"[;&|`]", cmd) or re.search(r"\$\(", cmd):
            return False
        return not is_dangerous(cmd)
    return False


SECRET_PATTERNS = [
    # Telegram bot tokens
    re.compile(r"\b\d{8,12}:AA[A-Za-z0-9_-]{30,}"),
    # OpenAI / Anthropic / Groq style keys
    re.compile(r"\b(?:sk-|gsk_)[A-Za-z0-9_-]{20,}"),
    # Google API keys: classic AIza... and new AQ. format (Gemini)
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"\bAQ\.[A-Za-z0-9_-]{20,}"),
    # JWTs
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    # PEM private keys
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
]

# NAME=value / NAME: value for secret-looking names -> keep the name, hide the value
_ASSIGNMENT = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PRIVATE_KEY|DATABASE_URL|REDIS_URL)[A-Z0-9_]*)"
    r"(\s*[:=]\s*[\"']?)([^\s\"',}]{8,})"
)


def redact_secrets(text):
    if not text:
        return text
    text = str(text)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return _ASSIGNMENT.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)


AUDIT_PATH = "state/exec_audit.json"


def audit(user_id, cmd, source, result):
    try:
        try:
            with open(AUDIT_PATH, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
        logs.append({"user": str(user_id), "cmd": redact_secrets(cmd), "source": source, "result": result, "time": time.time()})
        os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
        with open(AUDIT_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def run_gated(user_id, cmd, source="exec", timeout=15, max_output=4000):
    if not is_owner(user_id):
        return False, "Owner only."
    if not rate_limit_ok(user_id):
        return False, "Too fast."
    if is_dangerous(cmd):
        audit(user_id, cmd, source, "blocked")
        return False, "Command blocked."
    return _run(cmd, user_id, source, timeout, max_output)


def run_audit(user_id, cmd, source="audit", timeout=15, max_output=4000):
    if not is_admin(user_id):
        return False, "Admin only."
    if not rate_limit_ok(user_id):
        return False, "Too fast."
    if not is_audit_command(cmd):
        audit(user_id, cmd, source, "blocked_non_audit")
        return False, "Read-only audit command required."
    return _run(cmd, user_id, source, timeout, max_output)


def _run(cmd, user_id, source, timeout, max_output):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        output = redact_secrets((result.stdout or "") + (result.stderr or ""))
        if len(output) > max_output:
            output = output[:max_output] + "\n... truncated"
        audit(user_id, cmd, source, f"exit_{result.returncode}")
        return True, output or "(no output)"
    except Exception as e:
        audit(user_id, cmd, source, f"error_{type(e)}")
        return False, f"Error: {e}"