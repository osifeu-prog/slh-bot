"""Isolated, auditable economy for SLH agents.

This module never reads or mutates the existing user wallet ledger in
state/db.json. Agent economy state is stored separately and must be backed by
persistent storage in production.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
TREASURY_ACCOUNT = "AGENT_TREASURY"


class AgentEconomyService:
    _locks: dict[str, threading.RLock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, root="."):
        self.root = Path(root)
        self.state_dir = self.root / "state"
        self.path = self.state_dir / "agent_economy.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        key = str(self.path.resolve())
        with self._locks_guard:
            self._lock = self._locks.setdefault(key, threading.RLock())
        with self._lock:
            if not self.path.exists():
                self._write(self._initial_state())

    @staticmethod
    def _initial_state() -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "accounts": {TREASURY_ACCOUNT: 0.0},
            "ledger": [],
            "operations": {},
        }

    def _load(self) -> dict:
        if not self.path.exists():
            return self._initial_state()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("AGENT_ECONOMY_INVALID_STATE")
        if int(data.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("AGENT_ECONOMY_UNSUPPORTED_SCHEMA")
        accounts = data.setdefault("accounts", {})
        ledger = data.setdefault("ledger", [])
        operations = data.setdefault("operations", {})
        if not isinstance(accounts, dict) or not isinstance(ledger, list) or not isinstance(operations, dict):
            raise ValueError("AGENT_ECONOMY_INVALID_STATE")
        accounts.setdefault(TREASURY_ACCOUNT, 0.0)
        return data

    def _write(self, data: dict) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.state_dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _operation_fingerprint(payload: dict) -> str:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _operation_id(operation_id) -> str:
        value = str(operation_id or "").strip()
        if not value:
            raise ValueError("INVALID_OPERATION_ID")
        if len(value) > 128:
            raise ValueError("INVALID_OPERATION_ID")
        return value

    @staticmethod
    def _account_id(account_id) -> str:
        value = str(account_id or "").strip()
        if not value or len(value) > 128:
            raise ValueError("INVALID_AGENT_ACCOUNT")
        return value

    @staticmethod
    def _positive_amount(amount) -> float:
        value = float(amount)
        if not (value > 0) or value != value or value == float("inf") or value == float("-inf"):
            raise ValueError("INVALID_AMOUNT")
        return value

    def _lookup_operation(self, state: dict, operation_id: str, payload: dict):
        operation_id = self._operation_id(operation_id)
        fingerprint = self._operation_fingerprint(payload)
        existing = state["operations"].get(operation_id)
        if existing is None:
            return None, fingerprint
        if existing.get("fingerprint") != fingerprint:
            raise ValueError("OPERATION_ID_COLLISION")
        return existing, fingerprint

    def _record_operation(
        self,
        state: dict,
        operation_id: str,
        fingerprint: str,
        result: dict,
        *,
        kind: str,
    ) -> None:
        state["operations"][operation_id] = {
            "kind": kind,
            "status": str(result.get("status", "completed")),
            "fingerprint": fingerprint,
            "result": dict(result),
            "recorded_at": self._now(),
        }

    @staticmethod
    def _append_entry(
        state: dict,
        *,
        operation_id: str,
        account: str,
        counterparty: str | None,
        amount: float,
        before: float,
        after: float,
        actor: str,
        reason: str,
        entry_type: str,
        meta: dict | None = None,
    ) -> None:
        state["ledger"].append(
            {
                "timestamp": AgentEconomyService._now(),
                "operation_id": operation_id,
                "entry_type": entry_type,
                "account": account,
                "counterparty": counterparty,
                "amount": amount,
                "before": before,
                "after": after,
                "actor": str(actor),
                "reason": str(reason),
                "meta": dict(meta or {}),
            }
        )

    def balance(self, account_id: str) -> float:
        account_id = self._account_id(account_id)
        with self._lock:
            state = self._load()
            return float(state["accounts"].get(account_id, 0.0))

    def ledger(self) -> list[dict]:
        with self._lock:
            state = self._load()
            return [dict(row) for row in state["ledger"]]

    def record_revenue(
        self,
        *,
        amount,
        operation_id,
        actor,
        reason,
        evidence: dict,
        meta=None,
    ) -> dict:
        amount = self._positive_amount(amount)
        operation_id = self._operation_id(operation_id)
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("REVENUE_EVIDENCE_REQUIRED")

        payload = {
            "type": "revenue",
            "amount": amount,
            "actor": str(actor),
            "reason": str(reason),
            "evidence": evidence,
            "meta": dict(meta or {}),
        }

        with self._lock:
            state = self._load()
            existing, fingerprint = self._lookup_operation(state, operation_id, payload)
            if existing is not None:
                if existing.get("kind") != "revenue" or existing.get("status") != "completed":
                    raise ValueError("OPERATION_ID_COLLISION")
                result = dict(existing.get("result") or {})
                result["status"] = "duplicate"
                return result

            before = float(state["accounts"].get(TREASURY_ACCOUNT, 0.0))
            after = before + amount
            state["accounts"][TREASURY_ACCOUNT] = after

            self._append_entry(
                state,
                operation_id=operation_id,
                account=TREASURY_ACCOUNT,
                counterparty=None,
                amount=amount,
                before=before,
                after=after,
                actor=str(actor),
                reason=reason,
                entry_type="revenue",
                meta={"evidence": evidence, **dict(meta or {})},
            )

            result = {
                "status": "completed",
                "operation_id": operation_id,
                "account": TREASURY_ACCOUNT,
                "amount": amount,
                "balance": after,
            }
            self._record_operation(state, operation_id, fingerprint, result, kind="revenue")
            self._write(state)
            return result

    def propose_transfer(
        self,
        *,
        source_agent,
        target_agent,
        amount,
        operation_id,
        actor,
        reason,
        meta=None,
    ) -> dict:
        source_agent = self._account_id(source_agent)
        target_agent = self._account_id(target_agent)
        operation_id = self._operation_id(operation_id)
        amount = self._positive_amount(amount)
        if source_agent == target_agent:
            raise ValueError("SELF_TRANSFER")

        payload = {
            "type": "transfer",
            "source_agent": source_agent,
            "target_agent": target_agent,
            "amount": amount,
            "actor": str(actor),
            "reason": str(reason),
            "meta": dict(meta or {}),
        }

        with self._lock:
            state = self._load()
            existing, fingerprint = self._lookup_operation(state, operation_id, payload)
            if existing is not None:
                if existing.get("kind") == "transfer_proposal" and existing.get("status") == "proposed":
                    result = dict(existing.get("result") or {})
                    result["status"] = "already_proposed"
                    return result
                raise ValueError("OPERATION_ID_ALREADY_USED")

            source_balance = float(state["accounts"].get(source_agent, 0.0))
            if source_balance < amount:
                raise ValueError("INSUFFICIENT_AGENT_ECONOMY")

            result = {
                "status": "proposed",
                "operation_id": operation_id,
                "source_agent": source_agent,
                "target_agent": target_agent,
                "amount": amount,
                "source_balance": source_balance,
                "fingerprint": fingerprint,
            }
            self._record_operation(state, operation_id, fingerprint, result, kind="transfer_proposal")
            self._write(state)
            return result

    def transfer(
        self,
        *,
        source_agent,
        target_agent,
        amount,
        operation_id,
        actor,
        reason,
        meta=None,
    ) -> dict:
        source_agent = self._account_id(source_agent)
        target_agent = self._account_id(target_agent)
        operation_id = self._operation_id(operation_id)
        amount = self._positive_amount(amount)
        if source_agent == target_agent:
            raise ValueError("SELF_TRANSFER")

        payload = {
            "type": "transfer",
            "source_agent": source_agent,
            "target_agent": target_agent,
            "amount": amount,
            "actor": str(actor),
            "reason": str(reason),
            "meta": dict(meta or {}),
        }

        with self._lock:
            state = self._load()
            existing, fingerprint = self._lookup_operation(state, operation_id, payload)
            if existing is not None:
                kind = existing.get("kind")
                status = existing.get("status")
                if kind == "transfer" and status == "completed":
                    result = dict(existing.get("result") or {})
                    result["status"] = "duplicate"
                    return result
                if kind != "transfer_proposal" or status != "proposed":
                    raise ValueError("OPERATION_ID_COLLISION")

            source_before = float(state["accounts"].get(source_agent, 0.0))
            if source_before < amount:
                raise ValueError("INSUFFICIENT_AGENT_ECONOMY")
            target_before = float(state["accounts"].get(target_agent, 0.0))

            source_after = source_before - amount
            target_after = target_before + amount
            state["accounts"][source_agent] = source_after
            state["accounts"][target_agent] = target_after

            self._append_entry(
                state,
                operation_id=operation_id,
                account=source_agent,
                counterparty=target_agent,
                amount=-amount,
                before=source_before,
                after=source_after,
                actor=str(actor),
                reason=reason,
                entry_type="transfer_debit",
                meta=meta,
            )
            self._append_entry(
                state,
                operation_id=operation_id,
                account=target_agent,
                counterparty=source_agent,
                amount=amount,
                before=target_before,
                after=target_after,
                actor=str(actor),
                reason=reason,
                entry_type="transfer_credit",
                meta=meta,
            )

            result = {
                "status": "completed",
                "operation_id": operation_id,
                "source_agent": source_agent,
                "target_agent": target_agent,
                "amount": amount,
                "source_balance": source_after,
                "target_balance": target_after,
            }
            self._record_operation(state, operation_id, fingerprint, result, kind="transfer")
            self._write(state)
            return result

    def treasury_fund(
        self,
        *,
        agent_id,
        amount,
        operation_id,
        actor,
        reason,
        meta=None,
    ) -> dict:
        return self.transfer(
            source_agent=TREASURY_ACCOUNT,
            target_agent=self._account_id(agent_id),
            amount=amount,
            operation_id=operation_id,
            actor=actor,
            reason=reason,
            meta=meta,
        )

    def record_reward(
        self,
        *,
        agent_id,
        amount,
        operation_id,
        mission_id,
        actor,
        meta=None,
    ) -> dict:
        mission_id = str(mission_id or "").strip()
        if not mission_id:
            raise ValueError("INVALID_MISSION_ID")
        return self.treasury_fund(
            agent_id=agent_id,
            amount=amount,
            operation_id=operation_id,
            actor=actor,
            reason="mission:agent_reward",
            meta={"mission_id": mission_id, **dict(meta or {})},
        )