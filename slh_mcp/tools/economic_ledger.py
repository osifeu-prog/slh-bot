"""Canonical economic ledger MCP read tools."""

from __future__ import annotations

from core.economic_read_model import EconomicReadModel

from slh_mcp.auth import current_principal
from slh_mcp.core_client import configured_client


_MODEL = None


def _local_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = EconomicReadModel()
    return _MODEL


def _principal(principal=None):
    value = principal or current_principal()
    if value is None:
        raise PermissionError("MCP authentication required")
    return value


def economy_ledger(principal=None, limit: int = 100, domain: str | None = None, account_id: str | None = None) -> list[dict]:
    principal = _principal(principal)
    from slh_mcp.auth import authorize

    if not authorize(principal, "exec.audit"):
        raise PermissionError("ECONOMIC_LEDGER_FORBIDDEN")
    client = configured_client()
    if client is not None:
        return client.economic_ledger(limit=limit, domain=domain, account_id=account_id).get("events", [])
    return _local_model().events(limit=limit, domain=domain, account_id=account_id)


def economic_ledger_summary(principal=None) -> dict:
    principal = _principal(principal)
    from slh_mcp.auth import authorize

    if not authorize(principal, "exec.audit"):
        raise PermissionError("ECONOMIC_LEDGER_FORBIDDEN")
    client = configured_client()
    if client is not None:
        return client.economic_summary()
    return _local_model().summary()


def _tool_economy_ledger(
    limit: int = 100,
    domain: str | None = None,
    account_id: str | None = None,
):
    return economy_ledger(
        None,
        limit=limit,
        domain=domain,
        account_id=account_id,
    )