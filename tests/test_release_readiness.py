from core.release_readiness import build_release_report


def test_release_report_shape(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    report = build_release_report()

    assert report["overall_status"] in {"GREEN", "DEGRADED", "BLOCKED"}
    assert set(report["checks"]) == {
        "Telegram runtime",
        "AI intake",
        "Mini App auth",
        "Internal exchange",
        "Stars revenue",
        "External settlement gates",
        "Participation",
    }
    assert all(row["status"] in {"GREEN", "DEGRADED", "BLOCKED"} for row in report["checks"].values())


def test_release_report_allows_valid_open_ton(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("TON_DEPOSITS_OPEN", "1")
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")

    import core.ton_deposit_service as ton_service

    monkeypatch.setattr(
        ton_service,
        "ton_readiness",
        lambda: {"effective_open": True, "ready": True, "reasons": []},
    )

    import core.bnb_gate as bnb_gate
    import state_manager

    monkeypatch.setattr(
        bnb_gate,
        "bnb_readiness",
        lambda db=None: {
            "effective_open": False,
            "flag_open": False,
            "ready": True,
            "chain_id": 56,
            "confirmations_required": 15,
            "reasons": [],
        },
    )
    monkeypatch.setattr(
        bnb_gate,
        "bnb_opening_evidence",
        lambda: {
            "status": "BLOCKED",
            "ready_to_open": False,
            "gate_open": False,
            "next_action": "controlled_empirical_reconciliation_before_opening",
        },
    )
    monkeypatch.setattr(bnb_gate, "bnb_deposits_open", lambda: False)
    monkeypatch.setattr(state_manager, "load_db", lambda: {})

    report = build_release_report()
    check = report["checks"]["External settlement gates"]

    assert check["status"] == "DEGRADED"
    assert "TON settlement PUBLIC OPEN" in check["detail"]
    assert "BNB settlement remains CLOSED" in check["detail"]
    assert "empirical settlement proof pending/invalid" in check["detail"]


def test_release_report_blocks_bnb_operator_flag_without_revalidated_proof(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("TON_DEPOSITS_OPEN", "0")
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")

    import core.bnb_gate as bnb_gate
    import state_manager

    monkeypatch.setattr(
        bnb_gate,
        "bnb_readiness",
        lambda db=None: {
            "effective_open": True,
            "flag_open": True,
            "ready": True,
            "chain_id": 56,
            "confirmations_required": 15,
            "reasons": [],
        },
    )
    monkeypatch.setattr(
        bnb_gate,
        "bnb_opening_evidence",
        lambda: {
            "status": "BLOCKED",
            "ready_to_open": False,
            "gate_open": False,
            "next_action": "controlled_empirical_reconciliation_before_opening",
        },
    )
    monkeypatch.setattr(bnb_gate, "bnb_deposits_open", lambda: False)
    monkeypatch.setattr(state_manager, "load_db", lambda: {})

    report = build_release_report()
    check = report["checks"]["External settlement gates"]

    assert check["status"] == "BLOCKED"
    assert "BNB_DEPOSITS_OPEN=1" in check["detail"]
    assert "live empirical evidence is not valid" in check["detail"]


def test_release_report_green_bnb_only_after_revalidated_evidence_and_open_gate(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("TON_DEPOSITS_OPEN", "0")
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")

    import core.bnb_gate as bnb_gate
    import state_manager

    monkeypatch.setattr(
        bnb_gate,
        "bnb_readiness",
        lambda db=None: {
            "effective_open": True,
            "flag_open": True,
            "ready": True,
            "chain_id": 56,
            "confirmations_required": 15,
            "reasons": [],
        },
    )
    monkeypatch.setattr(
        bnb_gate,
        "bnb_opening_evidence",
        lambda: {
            "status": "READY_TO_OPEN",
            "ready_to_open": True,
            "gate_open": True,
            "next_action": "operator_may_review_bnb_gate_opening",
        },
    )
    monkeypatch.setattr(bnb_gate, "bnb_deposits_open", lambda: True)
    monkeypatch.setattr(state_manager, "load_db", lambda: {})

    report = build_release_report()
    check = report["checks"]["External settlement gates"]

    assert check["status"] == "GREEN"
    assert "BNB settlement PUBLIC OPEN" in check["detail"]
    assert "empirical evidence revalidated against chain and ledger" in check["detail"]
