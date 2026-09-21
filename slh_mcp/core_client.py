"""HTTP client for the canonical SLH Control Plane service.

In production, slh-mcp must point at the private web service so agents,
missions, and Agent Economy share one state authority.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlparse


class CoreControlPlaneClient:
    def __init__(self, base_url: str, internal_key: str, principal_id: str, timeout: float = 15.0):
        self.base_url = str(base_url).rstrip("/")
        self.internal_key = str(internal_key)
        self.principal_id = str(principal_id)
        self.timeout = float(timeout)

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, payload: dict | None = None) -> dict:
        return self._request("POST", path, payload=payload or {})

    def _request(self, method: str, path: str, *, params=None, payload=None) -> dict:
        path = "/" + str(path).lstrip("/")
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "SLH-MCP",
            "X-SLH-Internal-Key": self.internal_key,
            "X-SLH-Principal-Id": self.principal_id,
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw or "{}")
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8") or "{}")
            except Exception:
                detail = {}
            raise RuntimeError(
                f"CORE_API_HTTP_{exc.code}:{detail.get('error', 'unknown')}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("CORE_API_UNREACHABLE") from exc

    def agents(self) -> dict:
        return self.get("/api/internal/control-plane/agents")

    def agent(self, agent_id: str) -> dict:
        return self.get(f"/api/internal/control-plane/agents/{urllib.parse.quote(str(agent_id), safe='')}")

    def runtime(self) -> dict:
        return self.get("/api/internal/control-plane/runtime")

    def agent_execute(self, agent_id: str, command: str) -> dict:
        return self.post(
            f"/api/internal/control-plane/agents/{urllib.parse.quote(str(agent_id), safe='')}/execute",
            {"command": command},
        )

    def missions(self) -> dict:
        return self.get("/api/internal/control-plane/missions")

    def mission(self, mission_id: str) -> dict:
        return self.get(
            f"/api/internal/control-plane/missions/{urllib.parse.quote(str(mission_id), safe='')}"
        )

    def mission_complete(self, mission_id: str) -> dict:
        return self.post(
            f"/api/internal/control-plane/missions/{urllib.parse.quote(str(mission_id), safe='')}/complete",
            {},
        )

    def economy_balance(self, agent_id: str) -> dict:
        return self.get(
            f"/api/internal/control-plane/economy/{urllib.parse.quote(str(agent_id), safe='')}"
        )

    def economy_ledger(self, agent_id: str, limit: int = 100) -> dict:
        return self.get(
            f"/api/internal/control-plane/economy/{urllib.parse.quote(str(agent_id), safe='')}/ledger",
            {"limit": int(limit)},
        )

    def economy_propose(self, source_agent: str, target_agent: str, amount, operation_id: str, reason: str) -> dict:
        return self.post(
            "/api/internal/control-plane/economy/propose",
            {
                "source_agent": source_agent,
                "target_agent": target_agent,
                "amount": amount,
                "operation_id": operation_id,
                "reason": reason,
            },
        )

    def economy_transfer(self, source_agent: str, target_agent: str, amount, operation_id: str, reason: str) -> dict:
        return self.post(
            "/api/internal/control-plane/economy/transfer",
            {
                "source_agent": source_agent,
                "target_agent": target_agent,
                "amount": amount,
                "operation_id": operation_id,
                "reason": reason,
            },
        )

    def economic_ledger(self, limit: int = 100, domain: str | None = None, account_id: str | None = None) -> dict:
        params = {"limit": int(limit)}
        if domain:
            params["domain"] = str(domain)
        if account_id:
            params["account_id"] = str(account_id)
        return self.get("/api/internal/control-plane/economy/ledger", params)

    def economic_summary(self) -> dict:
        return self.get("/api/internal/control-plane/economy/summary")

    def economy_reward(self, agent_id: str, amount, operation_id: str, mission_id: str) -> dict:
        return self.post(
            "/api/internal/control-plane/economy/reward",
            {
                "agent_id": agent_id,
                "amount": amount,
                "operation_id": operation_id,
                "mission_id": mission_id,
            },
        )


def configured_client() -> CoreControlPlaneClient | None:
    base_url = str(os.getenv("SLH_CORE_API_URL", "")).strip()
    key = str(os.getenv("SLH_CORE_INTERNAL_KEY", "")).strip()
    principal_id = str(os.getenv("SLH_MCP_SERVICE_PRINCIPAL_ID", "slh-mcp")).strip()
    if not base_url or not key:
        return None
    return CoreControlPlaneClient(base_url, key, principal_id)