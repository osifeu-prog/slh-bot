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
            "ready": True,
            "chain_id": 56,
            "confirmations_required": 15,
            "reasons": [],
        },
    )
    monkeypatch.setattr(state_manager, "load_db", lambda: {})

    report = build_release_report()
    check = report["checks"]["External settlement gates"]

    assert check["status"] == "GREEN"
    assert "TON settlement PUBLIC OPEN" in check["detail"]
