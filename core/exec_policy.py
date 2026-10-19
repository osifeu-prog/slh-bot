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
]


AUDIT_ALLOWED_ROOT_FILES = {
    "README.md",
    "DEVELOPER_GUIDE.md",
    "DEVELOPER_ONBOARDING.md",
    "ARCHITECTURE.md",
    "API_REFERENCE.md",
    "ALPHA_CONTROL_PLANE.md",
}

AUDIT_ALLOWED_ROOTS = ("core/", "handlers/", "tests/", "slh_mcp/")
AUDIT_SENSITIVE_COMPONENTS = {"state", ".git", "proc", "sys", "dev"}


def _audit_path_allowed(path):
    """Allow only source-tree paths and explicitly approved root documents."""
    value = str(path or "").strip().strip("\"'")
    if not value or value in {".", "./", "/app", "/"} or value.startswith("/"):
        return False

    normalized = value.replace("\\\\", "/")
    components = [part.lower() for part in normalized.split("/") if part]
    if ".." in components:
        return False
    if any(
        part in AUDIT_SENSITIVE_COMPONENTS
        or part.startswith(".env")
        for part in components
    ):
        return False

    allowed_root_file = normalized in AUDIT_ALLOWED_ROOT_FILES
    allowed_source_root = normalized.startswith(AUDIT_ALLOWED_ROOTS)
    if not (allowed_root_file or allowed_source_root):
        return False

    # Reject symlinks in every existing path component, including the root,
    # so a lexical source path cannot redirect reads into runtime/secrets.
    current = os.getcwd()
    for component in normalized.split("/"):
        if not component:
            continue
        current = os.path.join(current, component)
        if os.path.islink(current):
            return False
    return True


def _audit_paths_safe(cmd):
    """Validate a small read-only command grammar before any process is started."""
    import shlex

    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return False
    if not tokens:
        return False

    command = tokens[0].lower()
    args = tokens[1:]

    if command in {"pwd", "whoami"}:
        return not args

    if command == "cat":
        return bool(args) and all(_audit_path_allowed(path) for path in args)

    if command in {"head", "tail"}:
        if args[:1] == ["-n"]:
            if len(args) < 3 or not args[1].isdigit():
                return False
            paths = args[2:]
        else:
            paths = args
        return bool(paths) and all(_audit_path_allowed(path) for path in paths)

    if command == "sed":
        # Permit only line-range printing; GNU sed's e/r/w commands are excluded.
        if len(args) != 3 or args[0] != "-n":
            return False
        if not re.fullmatch(r"(?:\d+|\$)(?:,(?:\d+|\$))?p", args[1]):
            return False
        return _audit_path_allowed(args[2])

    if command == "grep":
        # -R follows symlinks recursively; allow only -r, which does not.
        allowed_flags = {"-n", "-i", "-r", "-E", "-F", "-w", "-x", "-v"}
        index = 0
        while index < len(args) and args[index].startswith("-"):
            if args[index] not in allowed_flags:
                return False
            index += 1
        # Require an explicit search pattern and at least one approved source path.
        if index >= len(args) - 1:
            return False
        paths = args[index + 1:]
        return all(_audit_path_allowed(path) for path in paths)

    if command == "find":
        if not args or not _audit_path_allowed(args[0]):
            return False
        index = 1
        while index < len(args):
            flag = args[index]
            if flag == "-type":
                if index + 1 >= len(args) or args[index + 1] not in {"f", "d"}:
                    return False
                index += 2
            elif flag == "-name":
                if (
                    index + 1 >= len(args)
                    or "/" in args[index + 1]
                    or args[index + 1].startswith("-")
                ):
                    return False
                index += 2
            elif flag in {"-maxdepth", "-mindepth"}:
                if index + 1 >= len(args) or not args[index + 1].isdigit():
                    return False
                index += 2
            else:
                # In particular, reject -exec, -delete, -ok, and unknown predicates.
                return False
        return True

    return False


def is_audit_command(cmd):
    import shlex

    try:
        tokens = shlex.split(cmd)
    except (TypeError, ValueError):
        return False
    if not tokens:
        return False

    command = tokens[0].lower()
    if command not in {"whoami", "pwd", "grep", "find", "head", "tail", "cat", "sed"}:
        return False

    # The audit interface accepts command arguments, never shell syntax.
    if re.search(r"[;&|<>]", cmd) or chr(96) in cmd or re.search(r"\$\(", cmd):
        return False
    if is_dangerous(cmd):
        return False
    return _audit_paths_safe(cmd)


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
    return _run_audit(cmd, user_id, source, timeout, max_output)


def _run_audit(cmd, user_id, source, timeout, max_output):
    """Execute validated audit commands without invoking a shell."""
    import shlex

    try:
        argv = shlex.split(cmd)
        result = subprocess.run(
            argv, shell=False, capture_output=True, text=True, timeout=timeout
        )
        output = redact_secrets((result.stdout or "") + (result.stderr or ""))
        if len(output) > max_output:
            output = output[:max_output] + "\n... truncated"
        audit(user_id, cmd, source, f"exit_{result.returncode}")
        return True, output or "(no output)"
    except Exception as e:
        audit(user_id, cmd, source, f"error_{type(e).__name__}")
        return False, f"Error: {e}"


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