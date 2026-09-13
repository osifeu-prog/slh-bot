from core import staking_reward_settlement as settlement


def test_settlement_uses_economy_authority_and_is_recoverable(monkeypatch):
    db = {
        "users": {"u1": {"wallet": {"credits": 100}}},
        "stake_positions": {
            "sp1": {"uid": "u1", "amount": 100, "created_at": 0, "status": "locked"}
        },
        "reward_pools": {},
        "ledger": [],
    }
    calls = []

    def atomic_update(mutate):
        result = mutate(db)
        return result

    def record_transaction(uid, amount, reason, meta=None):
        calls.append((uid, amount, reason, dict(meta or {})))
        key = (meta or {}).get("idempotency_key")
        for entry in db["ledger"]:
            if entry.get("meta", {}).get("idempotency_key") == key:
                return entry["after"]
        before = db["users"][uid]["wallet"]["credits"]
        after = before + amount
        db["users"][uid]["wallet"]["credits"] = after
        db["ledger"].append({"before": before, "after": after, "amount": amount,
                              "reason": reason, "meta": dict(meta or {})})
        return after

    monkeypatch.setattr(settlement.state_manager, "atomic_update", atomic_update)
    monkeypatch.setattr(settlement.economy_service, "record_transaction", record_transaction)
    monkeypatch.setattr(settlement.time, "time", lambda: 86400.0)

    first = settlement.settle_position_reward("sp1", rate_per_day=0.001)
    second = settlement.settle_position_reward("sp1", rate_per_day=0.001)

    assert first["status"] == "settled"
    assert second["amount"] == 0
    assert db["users"]["u1"]["wallet"]["credits"] == 100.1
    assert len(calls) == 1
    assert db["reward_pools"]["sp1"]["settled_total"] == 0.1
