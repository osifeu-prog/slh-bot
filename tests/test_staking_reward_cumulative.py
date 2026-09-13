from core import reward_engine


def test_reward_claim_is_cumulative_and_idempotent(monkeypatch):
    db = {
        "users": {"u1": {"wallet": {"credits": 100}}},
        "stake_positions": {
            "sp1": {"uid": "u1", "amount": 100, "created_at": 0, "status": "locked"}
        },
        "reward_pools": {},
        "ledger": [],
    }
    now = iter([86400.0, 86400.0, 172800.0, 172800.0])
    credits_calls = []

    def atomic_update(mutate):
        return mutate(db)

    def add_credits(uid, amount, reason, meta=None):
        credits_calls.append((uid, amount, reason, dict(meta or {})))
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

    monkeypatch.setattr(reward_engine.state_manager, "atomic_update", atomic_update)
    monkeypatch.setattr(reward_engine.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(reward_engine.time, "time", lambda: next(now))
    monkeypatch.setattr(reward_engine.economy_bridge, "add_credits", add_credits)

    first_pool = reward_engine.accrue("sp1", rate_per_day=0.001)
    first = reward_engine.claim_reward("sp1")
    second_pool = reward_engine.accrue("sp1", rate_per_day=0.001)
    second = reward_engine.claim_reward("sp1")

    assert first_pool["reward"] == 0.1
    assert first["status"] == "paid"
    assert second_pool["reward"] == 0.1
    assert second["status"] == "paid"
    assert [round(c[1], 6) for c in credits_calls] == [0.1, 0.1]
    assert db["users"]["u1"]["wallet"]["credits"] == 100.2
    assert db["reward_pools"]["sp1"]["settled_total"] == 0.2
