from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(".").resolve()
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "_slh_audit" / f"phase1_authority_backup_{STAMP}"
BACKUP.mkdir(parents=True, exist_ok=True)

FILES = [
    "core/authority.py",
    "admin_utils.py",
    "core/firewall.py",
    "core/exec_policy.py",
    "core/identity.py",
    "security/permissions.py",
    "handlers/admin_extras.py",
    "handlers/dev_admin.py",
    "handlers/autoexec_handler.py",
    "handlers/deploy_handler.py",
    "handlers/bot_identity_handler.py",
]

for rel in FILES:
    src = ROOT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

print(f"BACKUP: {BACKUP}")

# ------------------------------------------------------------
# 1. CANONICAL AUTHORITY
# ------------------------------------------------------------

(ROOT / "core/authority.py").write_text(
'''"""SLH OS — canonical authority and permission gate.

This module is the single source of truth for identity, roles and
authorization decisions. Runtime handlers must not maintain their own
OWNER/ADMIN lists.
"""

from core.identity import OWNER_TELEGRAM_ID

OWNER_ID = str(OWNER_TELEGRAM_ID)
ADMIN_IDS = {OWNER_ID}

ROLES = {
    "OWNER": ["*"],
    "ADMIN": [
        "agents.view_all",
        "agents.manage",
        "exec.safe",
    ],
    "USER": [
        "agents.view_self",
        "exec.safe",
    ],
}


def normalize_uid(uid):
    if hasattr(uid, "from_user"):
        uid = getattr(uid.from_user, "id", uid)

    if isinstance(uid, dict):
        uid = uid.get("id") or uid.get("uid") or uid.get("user_id")

    if hasattr(uid, "id"):
        uid = uid.id

    return str(uid)


def is_owner(uid) -> bool:
    return normalize_uid(uid) == OWNER_ID


def get_role(uid) -> str:
    uid = normalize_uid(uid)

    if uid == OWNER_ID:
        return "OWNER"

    if uid in ADMIN_IDS:
        return "ADMIN"

    return "USER"


def has_permission(uid, permission: str) -> bool:
    role = get_role(uid)
    permissions = ROLES.get(role, [])

    return "*" in permissions or permission in permissions


def require_owner(uid) -> bool:
    return is_owner(uid)


def require_permission(uid, permission: str) -> bool:
    return has_permission(uid, permission)


def get_visible_agents(uid, agents: dict) -> dict:
    uid = normalize_uid(uid)

    if is_owner(uid):
        return agents

    visible = {}

    for aid, agent in agents.items():
        visibility = agent.get("visibility", "owner_and_self")
        owner = str(agent.get("owner_id", ""))

        if visibility == "owner_only":
            continue

        if owner == uid:
            visible[aid] = agent

        elif agent.get("agent_type") == "system":
            visible[aid] = {
                k: v
                for k, v in agent.items()
                if k not in ("inbox", "history", "permissions")
            }

    return visible
''',
encoding="utf-8"
)

# ------------------------------------------------------------
# 2. ADMIN UTILS
# ------------------------------------------------------------

(ROOT / "admin_utils.py").write_text(
'''from core.authority import (
    OWNER_ID,
    ADMIN_IDS,
    is_owner,
    get_role,
    has_permission,
)

_ADMIN_IDS = list(ADMIN_IDS)


def is_admin(m):
    return is_owner(m)


def get_owner():
    return int(OWNER_ID)
''',
encoding="utf-8"
)

# ------------------------------------------------------------
# 3. SECURITY PERMISSIONS -> AUTHORITY
# ------------------------------------------------------------

(ROOT / "security/permissions.py").write_text(
'''"""Compatibility permission API backed by core.authority."""

from core.authority import (
    is_owner,
    get_role as _authority_get_role,
    has_permission as _authority_has_permission,
    normalize_uid,
)


def _extract_uid(user_or_msg):
    return normalize_uid(user_or_msg)


def _is_owner(uid):
    return is_owner(uid)


def get_role(uid):
    role = _authority_get_role(uid)

    # Preserve legacy lowercase role API used by existing handlers.
    return role.lower() if role else None


def get_permissions(uid):
    from core.authority import ROLES

    role = _authority_get_role(uid)
    return list(ROLES.get(role, []))


def is_admin(user_or_msg):
    return is_owner(user_or_msg)


def has_permission(user_or_msg, permission):
    return _authority_has_permission(user_or_msg, permission)
''',
encoding="utf-8"
)

# ------------------------------------------------------------
# 4. FIREWALL
# ------------------------------------------------------------

(ROOT / "core/firewall.py").write_text(
'''import json
from pathlib import Path
from datetime import datetime, timezone

from core.authority import is_owner, has_permission, get_role

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "state" / "db.json"
FIREWALL_LOG = BASE_DIR / "state" / "firewall.jsonl"


def load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8-sig"))


def get_user(uid):
    db = load_db()
    return db.get("users", {}).get(str(uid), {})


def log_deny(uid, command, reason):
    FIREWALL_LOG.parent.mkdir(parents=True, exist_ok=True)

    with FIREWALL_LOG.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "uid": str(uid),
                    "command": command,
                    "decision": "DENIED",
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            )
            + "\\n"
        )


def require_owner(uid, command):
    if is_owner(uid):
        return True

    log_deny(uid, command, "not_owner")
    return False


def require_permission(uid, permission, command):
    if has_permission(uid, permission):
        return True

    log_deny(uid, command, f"missing_{permission}")
    return False


def firewall_status(uid):
    user = get_user(uid)

    return {
        "role": get_role(uid),
        "is_owner": is_owner(uid),
        "permissions": user.get("permissions", []),
    }
''',
encoding="utf-8"
)

# ------------------------------------------------------------
# 5. EXEC POLICY OWNER -> AUTHORITY
# ------------------------------------------------------------

p = ROOT / "core/exec_policy.py"
text = p.read_text(encoding="utf-8")

text = text.replace(
    'from core.identity import OWNER_TELEGRAM_ID',
    'from core.authority import is_owner as authority_is_owner'
)

text = text.replace(
'''def is_owner(user_id) -> bool:
    return int(user_id) == int(OWNER_TELEGRAM_ID)
''',
'''def is_owner(user_id) -> bool:
    return authority_is_owner(user_id)
'''
)

p.write_text(text, encoding="utf-8")

# ------------------------------------------------------------
# 6. ADMIN EXTRAS
# ------------------------------------------------------------

p = ROOT / "handlers/admin_extras.py"
text = p.read_text(encoding="utf-8")

text = text.replace(
    'from core.identity import OWNER_TELEGRAM_ID',
    'from core.authority import is_owner'
)

text = text.replace(
    'if int(m.from_user.id) != int(OWNER_TELEGRAM_ID):',
    'if not is_owner(m):'
)

p.write_text(text, encoding="utf-8")

# ------------------------------------------------------------
# 7. DEV ADMIN
# ------------------------------------------------------------

p = ROOT / "handlers/dev_admin.py"
text = p.read_text(encoding="utf-8")

text = text.replace(
    'from security.permissions import get_role, get_permissions, has_permission',
    'from security.permissions import get_role, get_permissions, has_permission\\nfrom core.authority import is_owner'
)

text = text.replace(
    'OWNER_TELEGRAM_ID = 8789977826\\n',
    ''
)

text = text.replace(
    'if m.from_user.id != OWNER_TELEGRAM_ID:',
    'if not is_owner(m):'
)

p.write_text(text, encoding="utf-8")

# ------------------------------------------------------------
# 8. AUTOEXEC -> GATED EXECUTION
# ------------------------------------------------------------

(ROOT / "handlers/autoexec_handler.py").write_text(
'''from core.authority import is_owner
from core.exec_policy import run_gated


def register(bot, context=None):

    @bot.message_handler(commands=["autoexec"])
    def autoexec_cmd(m):

        if not is_owner(m):
            bot.reply_to(m, "⛔ Owner only.")
            return

        lines = (m.text or "").split("\\n")
        output = []
        i = 1

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            if line.startswith("/exec_batch"):
                batch = []
                i += 1

                while i < len(lines) and lines[i].strip() != "/endbatch":
                    batch.append(lines[i])
                    i += 1

                if i >= len(lines):
                    output.append("❌ Missing /endbatch")
                    break

                cmd = "\\n".join(batch)

                ok, result = run_gated(
                    m.from_user.id,
                    cmd,
                    source="telegram:autoexec:batch",
                    timeout=30,
                )

                if not ok:
                    output.append(f"❌ BATCH BLOCKED/FAILED\\n{result}")
                    break

                output.append(f"✅ BATCH\\n{result}")

            elif line.startswith("/exec "):
                cmd = line[6:]

                ok, result = run_gated(
                    m.from_user.id,
                    cmd,
                    source="telegram:autoexec",
                    timeout=15,
                )

                if not ok:
                    output.append(f"❌ {cmd}\\n{result}")
                    break

                output.append(f"✅ {cmd}\\n{result}")

            i += 1

        bot.reply_to(
            m,
            "\\n\\n".join(output)[:4000]
            if output
            else "ℹ️ No commands found.",
        )
''',
encoding="utf-8"
)

# ------------------------------------------------------------
# 9. DEPLOY -> CANONICAL OWNER
# ------------------------------------------------------------

p = ROOT / "handlers/deploy_handler.py"
text = p.read_text(encoding="utf-8")

text = text.replace(
    'import requests',
    'import requests\\nfrom core.authority import is_owner'
)

text = text.replace(
    "if str(msg.from_user.id) != os.getenv('ADMIN_ID', '8789977826'):",
    "if not is_owner(msg):"
)

p.write_text(text, encoding="utf-8")

# ------------------------------------------------------------
# 10. BOT IDENTITY -> CANONICAL OWNER
# ------------------------------------------------------------

(ROOT / "handlers/bot_identity_handler.py").write_text(
'''import json
from pathlib import Path

from core.authority import is_owner

DB_PATH = Path("state/db.json")


def load_db():
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    with DB_PATH.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def register(bot):

    @bot.message_handler(commands=["botname"])
    def botname_cmd(msg):

        if not is_owner(msg):
            bot.reply_to(msg, "⛔ OWNER only.")
            return

        parts = msg.text.split(maxsplit=1)

        db = load_db()
        system = db.setdefault("system", {})

        if len(parts) == 1:
            bot.reply_to(
                msg,
                f"Current name: {system.get('bot_name', 'SLH OS AI')}\\n"
                "Usage: /botname <new name>",
            )
            return

        old = system.get("bot_name", "SLH OS AI")
        new = parts[1].strip()

        system["bot_name"] = new
        system["owner"] = "Osif"
        system["description"] = "SLH OS AI"

        save_db(db)

        bot.reply_to(
            msg,
            f"✅ Bot name changed\\nOld: {old}\\nNew: {new}",
        )


    @bot.message_handler(commands=["botinfo"])
    def botinfo_cmd(msg):

        db = load_db()
        system = db.get("system", {})

        bot.reply_to(
            msg,
            f"🤖 {system.get('bot_name', 'SLH OS AI')}\\n"
            f"👤 Owner: {system.get('owner', 'unknown')}\\n"
            f"ℹ️ {system.get('description', '')}",
        )


    print("✅ bot_identity_handler loaded")
''',
encoding="utf-8"
)

print()
print("=" * 60)
print("PHASE 1 AUTHORITY REPAIR APPLIED")
print("=" * 60)
print("Backup:", BACKUP)
print("Canonical authority: core/authority.py")
print("AUTOEXEC: routed through run_gated")
print("OWNER checks: centralized")
print("=" * 60)
