"""PostgreSQL backend for the isolated SLH agent economy.

This backend stores only Agent Economy records. It never touches the existing
user wallet ledger in state/db.json.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import psycopg
from psycopg.rows import dict_row


SCHEMA = """
CREATE TABLE IF NOT EXISTS slh_agent_accounts (
    account_id TEXT PRIMARY KEY,
    balance NUMERIC(30, 8) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS slh_agent_operations (
    operation_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    result JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS slh_agent_ledger (
    id BIGSERIAL PRIMARY KEY,
    operation_id TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    account_id TEXT NOT NULL,
    counterparty_id TEXT,
    amount NUMERIC(30, 8) NOT NULL,
    before_balance NUMERIC(30, 8) NOT NULL,
    after_balance NUMERIC(30, 8) NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_slh_agent_ledger_account_time
    ON slh_agent_ledger (account_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_slh_agent_ledger_operation
    ON slh_agent_ledger (operation_id);
"""


class PostgresAgentEconomyService:
    def __init__(self, database_url: str):
        database_url = str(database_url or "").strip()
        if not database_url:
            raise ValueError("AGENT_ECONOMY_DATABASE_URL_REQUIRED")
        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _operation_id(operation_id) -> str:
        value = str(operation_id or "").strip()
        if not value or len(value) > 128:
            raise ValueError("INVALID_OPERATION_ID")
        return value

    @staticmethod
    def _account_id(account_id) -> str:
        value = str(account_id or "").strip()
        if not value or len(value) > 128:
            raise ValueError("INVALID_AGENT_ACCOUNT")
        return value

    @staticmethod
    def _positive_amount(amount) -> Decimal:
        try:
            value = Decimal(str(amount))
        except (InvalidOperation, TypeError):
            raise ValueError("INVALID_AMOUNT")
        if not value.is_finite() or value <= 0:
            raise ValueError("INVALID_AMOUNT")
        return value.quantize(Decimal("0.00000001"))

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _json_result(result: dict) -> dict:
        return json.loads(json.dumps(result, default=str))

    def _ensure_schema(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
                cur.execute(
                    """
                    INSERT INTO slh_agent_accounts(account_id, balance)
                    VALUES (%s, 0)
                    ON CONFLICT (account_id) DO NOTHING
                    """,
                    ("AGENT_TREASURY",),
                )
            conn.commit()

    def _lookup_operation(self, cur, operation_id: str, fingerprint: str):
        cur.execute(
            """
            SELECT operation_id, kind, status, fingerprint, result
            FROM slh_agent_operations
            WHERE operation_id = %s
            FOR UPDATE
            """,
            (operation_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        if row["fingerprint"] != fingerprint:
            raise ValueError("OPERATION_ID_COLLISION")
        return row

    def balance(self, account_id: str) -> float:
        account_id = self._account_id(account_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT balance FROM slh_agent_accounts WHERE account_id=%s",
                    (account_id,),
                )
                row = cur.fetchone()
        return float(row["balance"]) if row else 0.0

    def ledger(self) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT operation_id, entry_type, account_id AS account,
                           counterparty_id AS counterparty, amount,
                           before_balance AS before, after_balance AS after,
                           actor, reason, meta, timestamp
                    FROM slh_agent_ledger
                    ORDER BY id ASC
                    """
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def _record_operation(self, cur, operation_id, kind, status, fingerprint, result):
        cur.execute(
            """
            INSERT INTO slh_agent_operations
                (operation_id, kind, status, fingerprint, result)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                operation_id,
                kind,
                status,
                fingerprint,
                json.dumps(self._json_result(result), ensure_ascii=False),
            ),
        )

    def _append_entry(
        self,
        cur,
        *,
        operation_id,
        entry_type,
        account,
        counterparty,
        amount,
        before,
        after,
        actor,
        reason,
        meta=None,
    ):
        cur.execute(
            """
            INSERT INTO slh_agent_ledger
                (operation_id, entry_type, account_id, counterparty_id,
                 amount, before_balance, after_balance, actor, reason, meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                operation_id,
                entry_type,
                account,
                counterparty,
                str(amount),
                str(before),
                str(after),
                str(actor),
                str(reason),
                json.dumps(meta or {}, ensure_ascii=False),
            ),
        )

    def record_revenue(self, *, amount, operation_id, actor, reason, evidence, meta=None):
        amount = self._positive_amount(amount)
        operation_id = self._operation_id(operation_id)
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("REVENUE_EVIDENCE_REQUIRED")

        payload = {
            "type": "revenue",
            "amount": str(amount),
            "actor": str(actor),
            "reason": str(reason),
            "evidence": evidence,
            "meta": dict(meta or {}),
        }
        fingerprint = self._fingerprint(payload)

        with self._connect() as conn:
            with conn.cursor() as cur:
                existing = self._lookup_operation(cur, operation_id, fingerprint)
                if existing:
                    if existing["kind"] != "revenue" or existing["status"] != "completed":
                        raise ValueError("OPERATION_ID_COLLISION")
                    result = dict(existing["result"])
                    result["status"] = "duplicate"
                    return result

                cur.execute(
                    """
                    INSERT INTO slh_agent_accounts(account_id, balance)
                    VALUES (%s, 0)
                    ON CONFLICT (account_id) DO NOTHING
                    """,
                    ("AGENT_TREASURY",),
                )
                cur.execute(
                    """
                    SELECT balance
                    FROM slh_agent_accounts
                    WHERE account_id=%s
                    FOR UPDATE
                    """,
                    ("AGENT_TREASURY",),
                )
                before = Decimal(str(cur.fetchone()["balance"]))
                after = before + amount
                cur.execute(
                    "UPDATE slh_agent_accounts SET balance=%s WHERE account_id=%s",
                    (str(after), "AGENT_TREASURY"),
                )
                self._append_entry(
                    cur,
                    operation_id=operation_id,
                    entry_type="revenue",
                    account="AGENT_TREASURY",
                    counterparty=None,
                    amount=amount,
                    before=before,
                    after=after,
                    actor=actor,
                    reason=reason,
                    meta={"evidence": evidence, **dict(meta or {})},
                )
                result = {
                    "status": "completed",
                    "operation_id": operation_id,
                    "account": "AGENT_TREASURY",
                    "amount": float(amount),
                    "balance": float(after),
                }
                self._record_operation(
                    cur, operation_id, "revenue", "completed", fingerprint, result
                )
            conn.commit()
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
    ):
        source_agent = self._account_id(source_agent)
        target_agent = self._account_id(target_agent)
        amount = self._positive_amount(amount)
        operation_id = self._operation_id(operation_id)
        if source_agent == target_agent:
            raise ValueError("SELF_TRANSFER")

        payload = {
            "type": "transfer",
            "source_agent": source_agent,
            "target_agent": target_agent,
            "amount": str(amount),
            "actor": str(actor),
            "reason": str(reason),
            "meta": dict(meta or {}),
        }
        fingerprint = self._fingerprint(payload)

        with self._connect() as conn:
            with conn.cursor() as cur:
                existing = self._lookup_operation(cur, operation_id, fingerprint)
                if existing:
                    if existing["kind"] == "transfer_proposal" and existing["status"] == "proposed":
                        result = dict(existing["result"])
                        result["status"] = "already_proposed"
                        return result
                    raise ValueError("OPERATION_ID_ALREADY_USED")

                cur.execute(
                    "SELECT balance FROM slh_agent_accounts WHERE account_id=%s FOR UPDATE",
                    (source_agent,),
                )
                row = cur.fetchone()
                source_balance = Decimal(str(row["balance"])) if row else Decimal("0")
                if source_balance < amount:
                    raise ValueError("INSUFFICIENT_AGENT_ECONOMY")

                result = {
                    "status": "proposed",
                    "operation_id": operation_id,
                    "source_agent": source_agent,
                    "target_agent": target_agent,
                    "amount": float(amount),
                    "source_balance": float(source_balance),
                }
                self._record_operation(
                    cur, operation_id, "transfer_proposal", "proposed", fingerprint, result
                )
            conn.commit()
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
    ):
        source_agent = self._account_id(source_agent)
        target_agent = self._account_id(target_agent)
        amount = self._positive_amount(amount)
        operation_id = self._operation_id(operation_id)
        if source_agent == target_agent:
            raise ValueError("SELF_TRANSFER")

        payload = {
            "type": "transfer",
            "source_agent": source_agent,
            "target_agent": target_agent,
            "amount": str(amount),
            "actor": str(actor),
            "reason": str(reason),
            "meta": dict(meta or {}),
        }
        fingerprint = self._fingerprint(payload)

        with self._connect() as conn:
            with conn.cursor() as cur:
                existing = self._lookup_operation(cur, operation_id, fingerprint)
                if existing:
                    if existing["kind"] == "transfer" and existing["status"] == "completed":
                        result = dict(existing["result"])
                        result["status"] = "duplicate"
                        return result
                    if existing["kind"] != "transfer_proposal" or existing["status"] != "proposed":
                        raise ValueError("OPERATION_ID_COLLISION")

                accounts = sorted({source_agent, target_agent})
                for account in accounts:
                    cur.execute(
                        """
                        INSERT INTO slh_agent_accounts(account_id, balance)
                        VALUES (%s, 0)
                        ON CONFLICT (account_id) DO NOTHING
                        """,
                        (account,),
                    )
                cur.execute(
                    """
                    SELECT account_id, balance
                    FROM slh_agent_accounts
                    WHERE account_id = ANY(%s)
                    ORDER BY account_id
                    FOR UPDATE
                    """,
                    (accounts,),
                )
                balances = {row["account_id"]: Decimal(str(row["balance"])) for row in cur.fetchall()}
                source_before = balances[source_agent]
                target_before = balances[target_agent]
                if source_before < amount:
                    raise ValueError("INSUFFICIENT_AGENT_ECONOMY")

                source_after = source_before - amount
                target_after = target_before + amount
                cur.execute(
                    "UPDATE slh_agent_accounts SET balance=%s WHERE account_id=%s",
                    (str(source_after), source_agent),
                )
                cur.execute(
                    "UPDATE slh_agent_accounts SET balance=%s WHERE account_id=%s",
                    (str(target_after), target_agent),
                )

                self._append_entry(
                    cur,
                    operation_id=operation_id,
                    entry_type="transfer_debit",
                    account=source_agent,
                    counterparty=target_agent,
                    amount=-amount,
                    before=source_before,
                    after=source_after,
                    actor=actor,
                    reason=reason,
                    meta=meta,
                )
                self._append_entry(
                    cur,
                    operation_id=operation_id,
                    entry_type="transfer_credit",
                    account=target_agent,
                    counterparty=source_agent,
                    amount=amount,
                    before=target_before,
                    after=target_after,
                    actor=actor,
                    reason=reason,
                    meta=meta,
                )

                result = {
                    "status": "completed",
                    "operation_id": operation_id,
                    "source_agent": source_agent,
                    "target_agent": target_agent,
                    "amount": float(amount),
                    "source_balance": float(source_after),
                    "target_balance": float(target_after),
                }
                self._record_operation(
                    cur, operation_id, "transfer", "completed", fingerprint, result
                )
            conn.commit()
        return result

    def treasury_fund(self, *, agent_id, amount, operation_id, actor, reason, meta=None):
        return self.transfer(
            source_agent="AGENT_TREASURY",
            target_agent=agent_id,
            amount=amount,
            operation_id=operation_id,
            actor=actor,
            reason=reason,
            meta=meta,
        )

    def record_reward(self, *, agent_id, amount, operation_id, mission_id, actor, meta=None):
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
