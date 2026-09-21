"""MCP tools for isolated agent economy."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents

from slh_mcp.agent_economy import AgentEconomyService
from slh_mcp.core_client import configured_client

_SERVICE = AgentEconomyService()


def _principal(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal
    value = current_principal()
    if value is None:
        raise PermissionError("MCP authentication required")
    return value


def _positive_amount(value) -> float:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError("INVALID_AMOUNT")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_AMOUNT")
    return float(amount)


def _owned(principal, agent_id: str) -> bool:
    visible = get_visible_agents(principal.subject, list_agents())
    canonical_id, record = get_agent(agent_id)
    if record is None or canonical_id not in visible:
        return False
    return str(principal.role) == "OWNER" or str(record.get("owner_id")) == str(principal.subject)


def economy_agent_balance(principal, agent_id: str) -> dict:
    principal = _principal(principal)
    client = configured_client()
    if client is not None:
        return dict(client.economy_balance(str(agent_id)))
    if not _owned(principal, str(agent_id)):
        raise PermissionError("AGENT_NOT_OWNED")
    return {
        "agent_id": str(agent_id),
        "balance": _SERVICE.balance(str(agent_id)),
        "currency": "agent_credits",
    }


def economy_agent_ledger(principal, agent_id: str, limit: int = 100) -> list[dict]:
    principal = _principal(principal)
    client = configured_client()
    if client is not None:
        return list(client.economy_ledger(str(agent_id), limit).get("ledger", []))
    if not _owned(principal, str(agent_id)):
        raise PermissionError("AGENT_NOT_OWNED")
    limit = int(limit)
    if limit < 1 or limit > 500:
        raise ValueError("INVALID_LIMIT")
    rows = [row for row in _SERVICE.ledger() if row.get("account") == str(agent_id)]
    return rows[-limit:]


def economy_propose_transfer(
    principal,
    source_agent: str,
    target_agent: str,
    amount,
    operation_id: str,
    reason: str = "agent_transfer",
) -> dict:
    principal = _principal(principal)
    client = configured_client()
    source_agent = str(source_agent).strip()
    target_agent = str(target_agent).strip()
    operation_id = str(operation_id).strip()
    reason = str(reason).strip()
    if not source_agent or not target_agent or not operation_id or not reason:
        raise ValueError("INVALID_TRANSFER_INPUT")
    if client is not None:
        return client.economy_propose(source_agent, target_agent, _positive_amount(amount), operation_id, reason)
    if not _owned(principal, source_agent):
        raise PermissionError("SOURCE_AGENT_NOT_OWNED")
    return _SERVICE.propose_transfer(
        source_agent=source_agent,
        target_agent=target_agent,
        amount=_positive_amount(amount),
        operation_id=operation_id,
        actor=principal.subject,
        reason=reason,
    )


def economy_commit_transfer(
    principal,
    source_agent: str,
    target_agent: str,
    amount,
    operation_id: str,
    reason: str = "agent_transfer",
) -> dict:
    principal = _principal(principal)
    client = configured_client()
    source_agent = str(source_agent).strip()
    target_agent = str(target_agent).strip()
    operation_id = str(operation_id).strip()
    reason = str(reason).strip()
    if not source_agent or not target_agent or not operation_id or not reason:
        raise ValueError("INVALID_TRANSFER_INPUT")
    if client is not None:
        return client.economy_transfer(source_agent, target_agent, _positive_amount(amount), operation_id, reason)
    if not _owned(principal, source_agent):
        raise PermissionError("SOURCE_AGENT_NOT_OWNED")
    return _SERVICE.transfer(
        source_agent=source_agent,
        target_agent=target_agent,
        amount=_positive_amount(amount),
        operation_id=operation_id,
        actor=principal.subject,
        reason=reason,
    )


def _tool_economy_agent_balance(agent_id: str):
    return economy_agent_balance(None, agent_id)


def _tool_economy_agent_ledger(agent_id: str, limit: int = 100):
    return economy_agent_ledger(None, agent_id, limit)


def _tool_economy_propose_transfer(
    source_agent: str,
    target_agent: str,
    amount: float,
    operation_id: str,
    reason: str = "agent_transfer",
):
    return economy_propose_transfer(
        None, source_agent, target_agent, amount, operation_id, reason
    )


def _tool_economy_commit_transfer(
    source_agent: str,
    target_agent: str,
    amount: float,
    operation_id: str,
    reason: str = "agent_transfer",
):
    return economy_commit_transfer(
        None, source_agent, target_agent, amount, operation_id, reason
    )