"""Isolated Agent Economy ledger.

This service is deliberately separate from the user financial state in
state/db.json. It records only agent-economy units and never imports or calls
user wallet mutation functions.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path


TREASURY_ACCOUNT = "AGENT_TREASURY"
SCHEMA_VERSION = 1


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
        raw = self.path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("agent economy state must be an object")
        if int(data.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("unsupported agent economy schema")
        data.setdefault("accounts", {})
        data.setdefault("ledger", [])
        data.setdefault("operations", {})
        if TREASURY_ACCOUNT not in data["accounts"]:
            data["accounts"][TREASURY_ACCOUNT] = 0.0
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
    def _operation_fingerprint(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _check_operation(self, state: dict, operation_id: str, payload: dict):
        operation_id = str(operation_id).strip()
        if not operation_id:
            raise ValueError("INVALID_OPERATION_ID")
        fingerprint = self._operation_fingerprint(payload)
        existing = state["operations"].get(operation_id)
        if existing is None:
            return None, fingerprint
        if existing.get("fingerprint") != fingerprint:
            raise ValueError("OPERATION_ID_COLLISION")
        return {"status": "duplicate", **existing.get("result", {})}, fingerprint

    def balance(self, account_id: str) -> float:
        account_id = str(account_id).strip()
        if not account_id:
            raise ValueError("INVALID_ACCOUNT_ID")
        with self._lock:
            state = self._load()
            return float(state["accounts"].get(account_id, 0.0))

    def ledger(self) -> list[dict]:
        with self._lock:
            state = self._load()
            return [dict(row) for row in state["ledger"]]

    def _append_entry(
        self,
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
        state["ledger"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        })

    def _record_operation(self, state: dict, operation_id: str, fingerprint: str, result: dict) -> None:
        state["operations"][operation_id] = {
            "fingerprint": fingerprint,
            "result": dict(result),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    def record_revenue(self, *, amount, operation_id, actor, reason, evidence: dict, meta=None) -> dict:
        amount = float(amount)
        if amount <= 0:
            raise ValueError("INVALID_REVENUE_AMOUNT")
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
            duplicate, fingerprint = self._check_operation(state, operation_id, payload)
            if duplicate:
                return duplicate
            before = float(state["accounts"].get(TREASURY_ACCOUNT, 0.0))
            after = before + amount
            state["accounts"][TREASURY_ACCOUNT] = after
            self._append_entry(
                state,
                operation_id=str(operation_id),
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
                "operation_id": str(operation_id),
                "account": TREASURY_ACCOUNT,
                "amount": amount,
                "balance": after,
            }
            self._record_operation(state, str(operation_id), fingerprint, result)
            self._write(state)
            return result

    def transfer(self, *, source_agent, target_agent, amount, operation_id, actor, reason, meta=None) -> dict:
        source_agent = str(source_agent).strip()
        target_agent = str(target_agent).strip()
        amount = float(amount)
        if not source_agent or not target_agent:
            raise ValueError("INVALID_AGENT_ACCOUNT")
        if source_agent == target_agent:
            raise ValueError("SELF_TRANSFER")
        if amount <= 0:
            raise ValueError("INVALID_TRANSFER_AMOUNT")
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
            duplicate, fingerprint = self._check_operation(state, operation_id, payload)
            if duplicate:
                return duplicate
            source_before = float(state["accounts"].get(source_agent, 0.0))
            if source_before < amount:
                raise ValueError("INSUFFICIENT_AGENT_ECONOMY")
            target_before = float(state["accounts"].get(target_agent, 0.0))
            source_after = source_before - amount
            target_after = target_before + amount
            state["accounts"][source_agent] = source_after
            state["accounts"][target_agent] = target_after
            operation_id = str(operation_id)
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
            self._record_operation(state, operation_id, fingerprint, result)
            self._write(state)
            return result

    def treasury_fund(self, *, agent_id, amount, operation_id, actor, reason, meta=None) -> dict:
        return self.transfer(
            source_agent=TREASURY_ACCOUNT,
            target_agent=str(agent_id),
            amount=amount,
            operation_id=operation_id,
            actor=actor,
            reason=reason,
            meta=meta,
        )
