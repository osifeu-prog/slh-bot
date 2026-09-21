"""Authentication and canonical SLH identity bridge for MCP."""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import os
from contextvars import ContextVar, Token
from typing import Mapping

from core.authority import ROLES, get_role, has_permission

from slh_mcp.security import redact


_CURRENT_PRINCIPAL: ContextVar[Principal | None] = ContextVar("slh_mcp_principal", default=None)


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    permissions: frozenset[str]

    @classmethod
    def from_headers(
        cls,
        headers: Mapping[str, str],
        expected: str | None,
        subject: str,
        role: str | None = None,
        permissions=(),
    ) -> "Principal | None":
        if not expected or not subject:
            return None

        authorization = str(
            headers.get("authorization")
            or headers.get("Authorization")
            or ""
        ).strip()

        scheme, _, token = authorization.partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            return None
        if not hmac.compare_digest(token, str(expected)):
            return None

        resolved_role = get_role(subject)
        resolved_permissions = frozenset(ROLES.get(resolved_role, ()))
        return cls(
            subject=str(subject),
            role=resolved_role,
            permissions=resolved_permissions,
        )


def principal_from_headers(headers: Mapping[str, str]) -> Principal | None:
    return Principal.from_headers(
        headers=headers,
        expected=os.getenv("SLH_MCP_BEARER_TOKEN"),
        subject=os.getenv("SLH_MCP_PRINCIPAL_ID", ""),
    )


def principal_from_scope(scope) -> Principal | None:
    raw_headers = {}
    for key, value in scope.get("headers", []):
        if isinstance(key, bytes):
            key = key.decode("latin-1")
        if isinstance(value, bytes):
            value = value.decode("latin-1")
        raw_headers[str(key).lower()] = str(value)
    return principal_from_headers(raw_headers)


def principal_from_request(request) -> Principal | None:
    return principal_from_headers(request.headers)


def set_current_principal(principal: Principal | None) -> Token:
    return _CURRENT_PRINCIPAL.set(principal)


def reset_current_principal(token: Token) -> None:
    _CURRENT_PRINCIPAL.reset(token)


def current_principal() -> Principal | None:
    return _CURRENT_PRINCIPAL.get()


def authorize(principal: Principal | None, permission: str) -> bool:
    if principal is None or not permission:
        return False
    return has_permission(principal.subject, permission)