from unittest.mock import patch

from core import bnb_empirical_smoke


UID = "8789977826"
TX = "0x" + "ab" * 32
ADDRESS = "0x1111111111111111111111111111111111111111"
TREASURY = "0x2222222222222222222222222222222222222222"


def test_owner_smoke_reconciles_real_path_and_replay():
    db = {
        "users": {UID: {"wallet": {"credits": 8.0}}},
        "ledger": [
            {
                "meta": {
                    "idempotency_key": f"bnb:deposit:{TX.lower()}",
                }
            },
        ],
        "settlement_evidence": {},
    }

    # Exercise the reconciliation algorithm deterministically while keeping
    # the production implementation untouched by the test's mocks.
    balances = iter([8.0, 18.0, 18.0])

    with patch.object(bnb_empirical_smoke, "is_owner", return_value=True), patch.object(
        bnb_empirical_smoke, "bnb_deposits_open", side_effect=[False, False]
    ), patch.object(
        bnb_empirical_smoke, "_existing_evidence", return_value=None
    ), patch.object(
        bnb_empirical_smoke, "get_binding", return_value={"address": ADDRESS}
    ), patch.object(
        bnb_empirical_smoke,
        "verify_bnb_deposit",
        return_value={
            "ok": True,
            "from": ADDRESS,
            "to": TREASURY,
            "amount_bnb": 0.01,
            "amount_wei": 10**16,
            "confirmations": 15,
        },
    ), patch.object(
        bnb_empirical_smoke, "get_balance_safe", side_effect=lambda _uid: next(balances)
    ), patch.object(
        bnb_empirical_smoke,
        "settle_bnb_deposit",
        side_effect=[
            {"credits": 10.0, "amount_wei": 10**16, "idempotent": False},
            {"credits": 10.0, "amount_wei": 10**16, "idempotent": True},
        ],
    ), patch.object(
        bnb_empirical_smoke.state_manager,
        "load_db",
        return_value=db,
    ), patch.object(
        bnb_empirical_smoke.state_manager,
        "atomic_update",
        side_effect=lambda fn: fn(db),
    ):
        result = bnb_empirical_smoke.run(UID, TX)

    assert result["status"] == "PASS"
    assert result["amount_wei"] == 10**16
    assert result["credits"] == 10.0
    assert result["balance_before"] == 8.0
    assert result["balance_after"] == 18.0
    assert result["replay_balance_after"] == 18.0
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


def test_stale_pass_evidence_does_not_block_new_valid_smoke_and_is_audited():
    old_tx = "0x" + "cd" * 32
    db = {
        "users": {UID: {"wallet": {"credits": 8.0}}},
        "ledger": [],
        "settlement_evidence": {
            "bnb": {
                "status": "PASS",
                "tx_hash": old_tx,
                "uid": UID,
                "credits": 10.0,
            }
        },
    }
    balances = iter([8.0, 18.0, 18.0])
    settled_calls = []

    def settle(uid, tx_hash):
        settled_calls.append(tx_hash)
        if len(settled_calls) == 1:
            db["ledger"].append({
                "uid": uid,
                "reason": "bnb:deposit",
                "amount": 10.0,
                "before": 8.0,
                "after": 18.0,
                "meta": {"idempotency_key": f"bnb:deposit:{tx_hash.lower()}"},
            })
            return {"credits": 10.0, "amount_wei": 10**16, "idempotent": False}
        return {"credits": 10.0, "amount_wei": 10**16, "idempotent": True}

    with patch.object(bnb_empirical_smoke, "is_owner", return_value=True), patch.object(
        bnb_empirical_smoke, "bnb_deposits_open", side_effect=[False, False]
    ), patch.object(
        bnb_empirical_smoke, "_existing_evidence", return_value=db["settlement_evidence"]["bnb"]
    ), patch(
        "core.bnb_gate._effective_config", return_value={"treasury_wallet": TREASURY}
    ), patch(
        "core.bnb_gate._empirical_evidence_revalidated", return_value=False
    ), patch.object(
        bnb_empirical_smoke, "get_binding", return_value={"address": ADDRESS}
    ), patch.object(
        bnb_empirical_smoke,
        "verify_bnb_deposit",
        return_value={
            "ok": True,
            "from": ADDRESS,
            "to": TREASURY,
            "amount_bnb": 0.01,
            "amount_wei": 10**16,
            "confirmations": 15,
        },
    ), patch.object(
        bnb_empirical_smoke, "get_balance_safe", side_effect=lambda _uid: next(balances)
    ), patch.object(
        bnb_empirical_smoke, "settle_bnb_deposit", side_effect=settle
    ), patch.object(
        bnb_empirical_smoke.state_manager, "load_db", return_value=db
    ), patch.object(
        bnb_empirical_smoke.state_manager, "atomic_update", side_effect=lambda fn: fn(db)
    ):
        result = bnb_empirical_smoke.run(UID, TX)

    assert result["status"] == "PASS"
    assert db["settlement_evidence"]["bnb"]["tx_hash"] == TX
    assert settled_calls == [TX, TX]
    assert len(db["settlement_evidence_audit"]) == 1
    assert db["settlement_evidence_audit"][0]["previous_tx_hash"] == old_tx
    assert db["settlement_evidence_audit"][0]["previous_status"] == "PASS"
    assert db["settlement_evidence_audit"][0]["disposition"] == "INVALIDATED_BY_REVALIDATION"
    assert db["settlement_evidence_audit"][0]["runtime_balance_unchanged_by_audit"] is True


def _existing_settled_db():
    return {
        "users": {UID: {"wallet": {"credits": 18.0}}},
        "ledger": [{
            "time": "2026-10-11T22:00:00+00:00",
            "uid": UID,
            "before": 8.0,
            "amount": 10.0,
            "after": 18.0,
            "reason": "bnb:deposit",
            "meta": {
                "idempotency_key": f"bnb:deposit:{TX.lower()}",
                "tx_hash": TX,
                "bnb_amount": 0.01,
                "bnb_amount_wei": 10**16,
                "from": ADDRESS,
                "to": TREASURY,
                "confirmations": 15,
            },
        }],
        "settlement_evidence": {},
        "settlement_evidence_audit": [],
    }


def test_existing_settlement_replay_creates_empirical_proof_without_recrediting():
    db = _existing_settled_db()
    balances = iter([18.0, 18.0])
    settlement = {
        "ok": True,
        "uid": UID,
        "tx_hash": TX,
        "amount_wei": 10**16,
        "credits": 0.0,
        "balance_after": 18.0,
        "idempotent": True,
        "settlement_status": "DUPLICATE",
        "binding": ADDRESS,
    }

    with patch.object(bnb_empirical_smoke, "is_owner", return_value=True), \
         patch.object(bnb_empirical_smoke, "bnb_deposits_open", side_effect=[False, False]), \
         patch.object(bnb_empirical_smoke, "get_binding", return_value={"address": ADDRESS}), \
         patch.object(bnb_empirical_smoke, "verify_bnb_deposit", return_value={
             "ok": True,
             "tx_hash": TX,
             "from": ADDRESS,
             "to": TREASURY,
             "amount_bnb": 0.01,
             "amount_wei": 10**16,
             "confirmations": 15,
         }), \
         patch.object(bnb_empirical_smoke, "get_balance_safe", side_effect=lambda _uid: next(balances)), \
         patch.object(bnb_empirical_smoke, "settle_bnb_deposit", return_value=settlement) as replay, \
         patch.object(bnb_empirical_smoke.state_manager, "load_db", return_value=db), \
         patch.object(bnb_empirical_smoke.state_manager, "atomic_update", side_effect=lambda mutate: mutate(db)), \
         patch("core.bnb_gate.bnb_readiness", return_value={"ready": True, "confirmations_required": 15}), \
         patch("core.bnb_gate.bnb_settlement_allowed", return_value=True), \
         patch("core.bnb_gate._effective_config", return_value={"treasury_wallet": TREASURY}), \
         patch("core.bnb_gate._empirical_evidence_revalidated", return_value=False):
        result = bnb_empirical_smoke.reconcile_existing_settlement(UID, TX)

    assert result["status"] == "PASS"
    assert result["proof_mode"] == "existing_ledger_plus_live_replay"
    assert result["credits"] == 10.0
    assert result["balance_before"] == 8.0
    assert result["balance_after"] == 18.0
    assert result["replay_balance_after"] == 18.0
    assert result["current_replay_balance_before"] == 18.0
    assert result["current_replay_balance_after"] == 18.0
    assert result["replay_observed_unchanged"] is True
    assert result["gate_remained_closed"] is True
    assert settlement["idempotent"] is True
    replay.assert_called_once_with(UID, TX)
    assert len(db["ledger"]) == 1
    assert db["users"][UID]["wallet"]["credits"] == 18.0
    assert db["settlement_evidence"]["bnb"]["status"] == "PASS"


def test_existing_settlement_replay_rejects_ambiguous_ledger_without_replay():
    db = _existing_settled_db()
    db["ledger"].append(dict(db["ledger"][0]))
    with patch.object(bnb_empirical_smoke, "is_owner", return_value=True), \
         patch.object(bnb_empirical_smoke.state_manager, "load_db", return_value=db), \
         patch.object(bnb_empirical_smoke, "bnb_deposits_open", return_value=False), \
         patch("core.bnb_gate.bnb_readiness", return_value={"ready": True, "confirmations_required": 15}), \
         patch("core.bnb_gate.bnb_settlement_allowed", return_value=True), \
         patch.object(bnb_empirical_smoke, "settle_bnb_deposit") as replay:
        result = bnb_empirical_smoke.reconcile_existing_settlement(UID, TX)

    assert result["status"] == "LEDGER_ENTRY_COUNT_MISMATCH"
    replay.assert_not_called()
    assert db["settlement_evidence"] == {}


def test_existing_settlement_replay_is_owner_only_before_chain_access():
    with patch.object(bnb_empirical_smoke, "is_owner", return_value=False), \
         patch.object(bnb_empirical_smoke, "verify_bnb_deposit") as verify, \
         patch.object(bnb_empirical_smoke, "settle_bnb_deposit") as replay:
        result = bnb_empirical_smoke.reconcile_existing_settlement("42", TX)

    assert result["status"] == "FORBIDDEN"
    verify.assert_not_called()
    replay.assert_not_called()
