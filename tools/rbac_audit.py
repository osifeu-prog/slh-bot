import sys
sys.path.insert(0,'.')

from security.permissions import has_permission

EXPECTED = {
    "8789977826": {
        "system_commands": True,
        "deploy": True,
        "db_write": True,
    },
    "224223270": {
        "exec_request": True,
        "read_logs": True,
        "db_read": True,
        "deploy": False,
        "db_write": False,
    },
    "7757102350": {
        "learning": False,
        "market": False,
        "exec_request": False,
        "deploy": False,
    }
}

failed = []

for uid, checks in EXPECTED.items():
    for permission, expected in checks.items():
        result = has_permission(uid, permission)
        if result != expected:
            failed.append(
                f"{uid} {permission}: got={result} expected={expected}"
            )

if failed:
    print("RBAC AUDIT FAILED")
    for x in failed:
        print(x)
    raise SystemExit(1)

print("RBAC AUDIT PASS")
