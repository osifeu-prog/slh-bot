"""Scoped read-only diagnostics for trusted ADMIN identities.

This module deliberately does not expose arbitrary shell execution. It provides
small, auditable checks that an ADMIN can use to investigate the SLH runtime
without receiving OWNER-level mutation privileges.
"""

from core.authority import has_permission, normalize_uid


ADMIN_AUDIT_PERMISSION = "exec.audit"


def can_audit(uid) -> bool:
    return has_permission(normalize_uid(uid), ADMIN_AUDIT_PERMISSION)


def deny_message():
    return "⛔️ ADMIN audit permission required."
