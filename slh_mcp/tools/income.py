"""MCP read-only Stars revenue reconciliation."""
from __future__ import annotations

from core import revenue_reconciliation
import state_manager
from slh_mcp.auth import authorize, current_principal


def income_reconciliation(principal=None) -> dict:
    if principal is None:
        from slh_mcp.auth import current_principal
        principal = current_principal()
    if principal is None:
        raise PermissionError("MCP authentication required")

    from slh_mcp.auth import authorize
    if not authorize(principal, "exec.audit"):
        raise PermissionError("INCOME_RECONCILIATION_FORBIDDEN")

    return revenue_reconciliation.audit(state_manager.load_db())


def _tool_income_reconciliation():
    return income_reconciliation()