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


def test_release_report_flags_open_ton(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("TON_DEPOSITS_OPEN", "1")
    report = build_release_report()

    check = report["checks"]["External settlement gates"]
    assert check["status"] == "BLOCKED"
    assert "TON_DEPOSITS_OPEN=1" in check["detail"]
