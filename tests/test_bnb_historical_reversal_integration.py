from copy import deepcopy
from unittest.mock import patch

from core.bnb_gate import _audit_historical_bnb_deposits

TX = "0x" + "ab" * 32
SELF = "0x2222222222222222222222222222222222222222"
TREASURY = "0x1111111111111111111111111111111111111111"


def _db(with_reversal=True):
    row = {
        "time": "2026-10-10T08:58:47+00:00",
        "uid": "8789977826",
        "before": 8.091775,
        "amount": 10.0,
        "after": 18.091775,
        "reason": "bnb:deposit",
        "meta": {
            "tx_hash": TX,
            "idempotency_key": f"bnb:deposit:{TX}",
            "bnb_amount_wei": 10**16,
            "from": SELF,
            "to": SELF,
        },
    }
    ledger = [row]
    if with_reversal:
        ledger.append({
            "uid": "8789977826",
            "before": 30.072775,
            "amount": -10.0,
            "after": 20.072775,
            "reason": "accounting:invalid_bnb_deposit_reversal",
            "meta": {"idempotency_key": f"accounting:reversal:{TX}"},
        })
    return {"ledger": ledger}


def test_history_gate_accepts_only_independently_audited_reversal(monkeypatch):
    db = _db()
    before = deepcopy(db)
    audit_result = {
        "scope": "read_only",
        "status": "PASS",
        "rows_found": 2,
        "rows_checked": 2,
        "failed_rows": 0,
        "blockers": [],
        "findings": [],
    }
    with patch(
        "core.deposit_monitor.verify_bnb_deposit",
        return_value={"ok": False, "error": "BNB_TX_RECIPIENT_NOT_TREASURY"},
    ), patch(
        "core.bnb_history_audit.audit_bnb_deposit_history",
        return_value=audit_result,
    ) as history_audit:
        result = _audit_historical_bnb_deposits(
            db, {"treasury_wallet": TREASURY, "confirmations": 15}
        )

    assert result["ok"] is True
    assert result["rows_checked"] == 1
    assert result["finding_count"] == 0
    history_audit.assert_called_once_with(db)
    assert db == before


def test_history_gate_stays_blocked_when_reversal_audit_is_blocked(monkeypatch):
    db = _db()
    with patch(
        "core.deposit_monitor.verify_bnb_deposit",
        return_value={"ok": False, "error": "BNB_TX_RECIPIENT_NOT_TREASURY"},
    ), patch(
        "core.bnb_history_audit.audit_bnb_deposit_history",
        return_value={
            "status": "BLOCKED",
            "rows_found": 1,
            "rows_checked": 1,
            "failed_rows": 1,
            "blockers": ["SELF_TRANSFER_NOT_A_DEPOSIT"],
            "findings": [{"tx_suffix": TX[-8:], "status": "BLOCKED"}],
        },
    ) as history_audit:
        result = _audit_historical_bnb_deposits(
            db, {"treasury_wallet": TREASURY, "confirmations": 15}
        )

    assert result["ok"] is False
    assert result["finding_count"] == 1
    assert "CHAIN_TX_NOT_VERIFIED" in result["findings"][0]["issues"]
    history_audit.assert_called_once_with(db)


def test_history_gate_does_not_use_reversal_fallback_without_matching_correction(monkeypatch):
    db = _db(with_reversal=False)
    with patch(
        "core.deposit_monitor.verify_bnb_deposit",
        return_value={"ok": False, "error": "BNB_TX_RECIPIENT_NOT_TREASURY"},
    ), patch(
        "core.bnb_history_audit.audit_bnb_deposit_history"
    ) as history_audit:
        result = _audit_historical_bnb_deposits(
            db, {"treasury_wallet": TREASURY, "confirmations": 15}
        )

    assert result["ok"] is False
    assert result["finding_count"] == 1
    history_audit.assert_not_called()
