from unittest.mock import patch

from core import bnb_empirical_smoke


UID = "8789977826"
TX = "0x" + "ab" * 32
ADDRESS = "0x1111111111111111111111111111111111111111"


def test_owner_smoke_reconciles_settlement_and_replay():
    db = {
        "users": {UID: {"wallet": {"credits": 8.0}}},
        "ledger": [],
        "settlement_evidence": {},
    }
    balances = iter([8.0, 9.0, 9.0])

    with patch.object(bnb_empirical_smoke, "is_owner", return_value=True),         patch.object(bnb_empirical_smoke, "bnb_deposits_open", return_value=False),         patch.object(bnb_empirical_smoke, "_existing_evidence", return_value=None),         patch.object(bnb_empirical_smoke, "get_binding", return_value={"address": ADDRESS}),         patch.object(
            bnb_empirical_smoke,
            "verify_bnb_deposit",
            return_value={
                "ok": True,
                "from": ADDRESS,
                "to": "0x2222222222222222222222222222222222222222",
                "amount_wei": 10**15,
                "amount_bnb": 0.001,
                "confirmations": 15,
            },
        ),         patch.object(bnb_empirical_smoke, "get_balance_safe", side_effect=lambda _uid: next(balances)),         patch.object(
            bnb_empirical_smoke,
            "settle_bnb_deposit",
            side_effect=[
                {"credits": 1.0, "amount_wei": 10**15, "idempotent": False},
                {"credits": 1.0, "amount_wei": 10**15, "idempotent": True},
            ],
        ),         patch.object(bnb_empirical_smoke.state_manager, "load_db", return_value=db),         patch.object(bnb_empirical_smoke.state_manager, "atomic_update", side_effect=lambda fn: fn(db)):
        result = bnb_empirical_smoke.run(UID, TX)

    assert result["status"] == "PASS"
    assert result["amount_wei"] == 10**15
    assert result["credits"] == 1.0
    assert result["balance_before"] == 8.0
    assert result["balance_after"] == 9.0
    assert result["replay_balance_after"] == 9.0
    assert result["ledger_entries_for_idempotency_key"] == 1
    assert result["gate_remained_closed"] is True
    assert db["settlement_evidence"]["bnb"]["status"] == "PASS"


def test_smoke_is_owner_only():
    with patch.object(bnb_empirical_smoke, "is_owner", return_value=False):
        try:
            bnb_empirical_smoke.run(UID, TX)
        except bnb_empirical_smoke.BNBEmpiricalSmokeError as exc:
            assert str(exc) == "BNB_EMPIRICAL_SMOKE_OWNER_ONLY"
        else:
            raise AssertionError("owner-only smoke must reject non-owner")
