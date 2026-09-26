def test_declared_bot_and_heartbeat(tmp_path, monkeypatch):
    import core.bot_registry as registry

    db_path = tmp_path / "db.json"
    db_path.write_text('{"users":{}}', encoding="utf-8")
    monkeypatch.setattr("state_manager.DB_PATH", db_path)

    row = registry.register_declared_bot(
        "@ExampleTradeBot",
        owner_id="1",
        name="Example Trade",
        role="trading",
    )
    assert row["status"] == "declared"
    assert row["health"] == "UNKNOWN"
    assert row["telemetry_status"] == "UNVERIFIED"

    healthy = registry.record_heartbeat(
        "@ExampleTradeBot",
        status="ok",
        details={"service": "test"},
    )
    assert healthy["health"] == "HEALTHY"
    assert healthy["telemetry_status"] == "VERIFIED"
    assert healthy["last_heartbeat_status"] == "ok"
