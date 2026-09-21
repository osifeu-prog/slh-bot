"""Authentication and canonical SLH identity bridge for MCP."""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import os
from typing import Mapping

from core.authority import ROLES, get_role, has_permission

from slh_mcp.security import redact


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

        authorization = ""
        for key, value in headers.items():
            if str(key).lower() == "authorization":
                authorization = str(value).strip()
                break

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


def principal_from_request(request) -> Principal | None:
    return principal_from_headers(request.headers)


def authorize(principal: Principal | None, permission: str) -> bool:
    if principal is None or not permission:
        return False
    return has_permission(principal.subject, permission)
