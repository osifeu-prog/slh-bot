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
    # Internal Credits also require canonical transaction/ledger authorities.
    # Block direct assignment and in-place arithmetic in owner /exec commands.
    r"""(?:\[\s*["']credits["']\s*\]|\.credits)\s*(?:\+=|-=|\*=|//=|/=|=)""",
    r"""\.update\(\s*\{[^}]*["']credits["']""",
    r"""\.setdefault\(\s*["']credits["']""",
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


AUDIT_FORBIDDEN_PATHS = (
    re.compile(r"(^|[\\s'\"=:/])(?:\\.?/)?state(?:/|$)", re.IGNORECASE),
    re.compile(r"(^|[\\s'\"=:/])(?:\\.?/)?\\.env(?:\\.|/|$)", re.IGNORECASE),
    re.compile(r"(^|[\\s'\"=:/])(?:\\.?/)?\\.git(?:/|$)", re.IGNORECASE),
    re.compile(r"(^|[\\s'\"=:/])/(?:proc|sys|dev)(?:/|$)", re.IGNORECASE),
)

AUDIT_ALLOWED_ROOT_FILES = {
    "README.md",
    "DEVELOPER_GUIDE.md",
    "DEVELOPER_ONBOARDING.md",
    "ARCHITECTURE.md",
    "API_REFERENCE.md",
    "ALPHA_CONTROL_PLANE.md",
}


def _audit_path_allowed(path):
    value = str(path or "").strip().strip("\"'")
    if not value or value in {".", "./", "/app", "/"}:
        return False
    if value.startswith("/"):
        return False
    if value in AUDIT_ALLOWED_ROOT_FILES:
        return True
    normalized = value.replace("\\\\", "/")
    return normalized.startswith(("core/", "handlers/", "tests/", "slh_mcp/"))


def _audit_paths_safe(cmd):
    """Reject sensitive runtime paths and unrestricted repository recursion."""
    if any(pattern.search(cmd) for pattern in AUDIT_FORBIDDEN_PATHS):
        return False

    try:
        import shlex
        tokens = shlex.split(cmd)
    except ValueError:
        return False

    if not tokens:
        return False

    command = tokens[0].lower()
    args = tokens[1:]

    if command == "find":
        roots = [x for x in args if not x.startswith("-")]
        return bool(roots) and _audit_path_allowed(roots[0])

    if command in {"cat", "head", "tail"}:
        paths = [x for x in args if not x.startswith("-")]
        return bool(paths) and all(_audit_path_allowed(x) for x in paths)

    if command == "sed":
        paths = [x for x in args[1:] if not x.startswith("-")]
        return bool(paths) and all(_audit_path_allowed(x) for x in paths)

    if command == "awk":
        paths = [x for x in args[1:] if not x.startswith("-")]
        return all(_audit_path_allowed(x) for x in paths) if paths else True

    if command == "grep":
        paths = [x for x in args if ("/" in x or x in {".", "./", "/app"})]
        return all(_audit_path_allowed(x) for x in paths) if paths else True

    return True


def is_audit_command(cmd):
    if any(re.search(p, cmd, re.IGNORECASE) for p in AUDIT_COMMAND_PATTERNS):
        # No command chaining, redirection, command substitution or writes.
        if re.search(r"[;&|]", cmd) or "`" in cmd or re.search(r"\$\(", cmd):
            return False
        if is_dangerous(cmd):
            return False
        return _audit_paths_safe(cmd)
    return False



SECRET_PATTERNS = [
    # Telegram bot tokens: token body is opaque; do not rely on a fixed prefix.
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
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

# Match secret-looking names in NAME=value and JSON/YAML-like "NAME": "value"
# output. Accept quotes around the key as well as around the value.
_ASSIGNMENT = re.compile(
    r"""(?i)(["']?\b[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE_KEY|DATABASE_URL|REDIS_URL|ACTIVATION_CODE|MQTT_USERNAME|SEED(?:[ _-]?PHRASE)?|MNEMONIC)[A-Z0-9_]*["']?)"""
    r"""(\s*[:=]\s*["']?)([^\s"',}]{8,})"""
)

# A recovery phrase may be printed as a bare line with no label. Restrict this
# fallback to standalone 12/24-word lowercase ASCII lines to limit false
# positives in ordinary prose. This is best-effort, not a wallet phrase parser.
_SEED_PHRASE_LINE = re.compile(
    r"(?im)^\s*(?:[\"']?(?:SEED(?:[ _-]?PHRASE)?|MNEMONIC)[\"']?\s*[:=]\s*)?(?:[a-z]{2,12}\s+){11}[a-z]{2,12}\s*$"
    r"|^\s*(?:[\"']?(?:SEED(?:[ _-]?PHRASE)?|MNEMONIC)[\"']?\s*[:=]\s*)?(?:[a-z]{2,12}\s+){23}[a-z]{2,12}\s*$"
)


def redact_secrets(text):
    if not text:
        return text
    text = str(text)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    text = _SEED_PHRASE_LINE.sub("[REDACTED RECOVERY PHRASE]", text)
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