import json
from unittest.mock import patch

import pytest

from core import miner_service


DEVICE_ID = "ESP32_TEST_01"
TOKEN = "test-miner-token"


def _payload(**overrides):
    payload = {
        "device_id": DEVICE_ID,
        "miner_id": "miner_01",
        "temp": 68.5,
        "watts": 3250,
        "volts": 230.1,
        "amps": 14.1,
        "kwh": 12.7,
        "status": "OK",
    }
    payload.update(overrides)
    return payload


def _db():
    return {
        "users": {"8789977826": {"wallet": {"credits": 7}}},
        "devices": {
            DEVICE_ID: {
                "device_id": DEVICE_ID,
                "owner_id": "8789977826",
                "type": "esp32",
                "status": "online",
                "mqtt_topics": {"telemetry": f"slh/esp/{DEVICE_ID}/telemetry"},
                "miner_enabled": True,
                "unrelated_field": "must survive",
            }
        },
        "ledger": [{"id": "unchanged"}],
    }


def _configure_global_token(monkeypatch):
    monkeypatch.delenv("SLH_MINER_DEVICE_TOKENS_JSON", raising=False)
    monkeypatch.delenv("SLH_MINER_DEVICE_IDS", raising=False)
    monkeypatch.setenv("SLH_MINER_INGEST_TOKEN", TOKEN)


def test_ingest_saves_to_existing_canonical_device_record_without_touching_ledger(monkeypatch):
    _configure_global_token(monkeypatch)
    db = _db()
    original_ledger = list(db["ledger"])
    original_user = dict(db["users"]["8789977826"])
    original_topics = dict(db["devices"][DEVICE_ID]["mqtt_topics"])

    with patch.object(miner_service.state_manager, "load_db", return_value=db), patch.object(
        miner_service.state_manager, "atomic_update", side_effect=lambda mutate: mutate(db)
    ) as atomic_update:
        saved = miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")

    device = db["devices"][DEVICE_ID]
    assert saved["device_id"] == DEVICE_ID
    assert saved["temperature_c"] == 68.5
    assert saved["watts"] == 3250.0
    assert saved["volts"] == 230.1
    assert saved["amps"] == 14.1
    assert saved["energy_kwh"] == 12.7
    assert saved["health_status"] == "OK"
    assert saved["alerts"] == []
    assert saved["source"] == "esp32_authenticated_http"
    assert saved["last_seen"].endswith("Z")
    assert device["telemetry"] == saved
    assert device["last_telemetry_at"] == saved["last_seen"]
    assert device["mqtt_topics"] == original_topics
    assert device["unrelated_field"] == "must survive"
    assert "miners" not in db
    assert db["ledger"] == original_ledger
    assert db["users"]["8789977826"] == original_user
    atomic_update.assert_called_once()


def test_ingest_derives_advisory_alerts_but_never_issues_hardware_commands(monkeypatch):
    _configure_global_token(monkeypatch)
    db = _db()
    with patch.object(miner_service.state_manager, "load_db", return_value=db), patch.object(
        miner_service.state_manager, "atomic_update", side_effect=lambda mutate: mutate(db)
    ):
        saved = miner_service.ingest_telemetry(_payload(temp=86, watts=0), f"Bearer {TOKEN}")

    assert saved["health_status"] == "ALERT"
    assert saved["alerts"] == ["TEMPERATURE_CRITICAL", "POWER_LOW_REVIEW"]
    assert "relay" not in saved
    assert "command" not in saved


def test_ingest_fails_closed_when_token_is_not_configured(monkeypatch):
    monkeypatch.delenv("SLH_MINER_INGEST_TOKEN", raising=False)
    monkeypatch.delenv("SLH_MINER_DEVICE_TOKENS_JSON", raising=False)
    with patch.object(miner_service.state_manager, "load_db") as load_db:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")
    assert exc.value.code == "MINER_INGEST_NOT_CONFIGURED"
    assert exc.value.status_code == 503
    load_db.assert_not_called()


def test_device_specific_token_is_required_when_token_map_is_configured(monkeypatch):
    monkeypatch.setenv("SLH_MINER_DEVICE_TOKENS_JSON", json.dumps({DEVICE_ID: "device-specific-token"}))
    monkeypatch.setenv("SLH_MINER_INGEST_TOKEN", TOKEN)
    db = _db()
    with patch.object(miner_service.state_manager, "load_db", return_value=db), patch.object(
        miner_service.state_manager, "atomic_update"
    ) as atomic_update:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")
    assert exc.value.code == "MINER_AUTH_INVALID"
    assert exc.value.status_code == 401
    atomic_update.assert_not_called()


def test_device_specific_token_is_accepted_as_explicit_device_opt_in(monkeypatch):
    monkeypatch.setenv("SLH_MINER_DEVICE_TOKENS_JSON", json.dumps({DEVICE_ID: "device-specific-token"}))
    monkeypatch.delenv("SLH_MINER_INGEST_TOKEN", raising=False)
    db = _db()
    db["devices"][DEVICE_ID].pop("miner_enabled")
    with patch.object(miner_service.state_manager, "load_db", return_value=db), patch.object(
        miner_service.state_manager, "atomic_update", side_effect=lambda mutate: mutate(db)
    ):
        saved = miner_service.ingest_telemetry(_payload(), "Bearer device-specific-token")
    assert saved["device_id"] == DEVICE_ID
    assert db["devices"][DEVICE_ID]["telemetry"]["temperature_c"] == 68.5


def test_device_allowlist_is_an_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("SLH_MINER_DEVICE_IDS", DEVICE_ID)
    monkeypatch.setenv("SLH_MINER_INGEST_TOKEN", TOKEN)
    db = _db()
    db["devices"][DEVICE_ID].pop("miner_enabled")
    with patch.object(miner_service.state_manager, "load_db", return_value=db), patch.object(
        miner_service.state_manager, "atomic_update", side_effect=lambda mutate: mutate(db)
    ):
        saved = miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")
    assert saved["device_id"] == DEVICE_ID


def test_ingest_rejects_unregistered_device_before_state_write(monkeypatch):
    _configure_global_token(monkeypatch)
    db = _db()
    db["devices"] = {}
    with patch.object(miner_service.state_manager, "load_db", return_value=db), patch.object(
        miner_service.state_manager, "atomic_update"
    ) as atomic_update:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")
    assert exc.value.code == "MINER_DEVICE_NOT_REGISTERED"
    assert exc.value.status_code == 404
    atomic_update.assert_not_called()


def test_ingest_rejects_generic_esp32_without_explicit_miner_opt_in(monkeypatch):
    _configure_global_token(monkeypatch)
    db = _db()
    db["devices"][DEVICE_ID].pop("miner_enabled")
    with patch.object(miner_service.state_manager, "load_db", return_value=db), patch.object(
        miner_service.state_manager, "atomic_update"
    ) as atomic_update:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")
    assert exc.value.code == "MINER_ROLE_NOT_ENABLED"
    assert exc.value.status_code == 403
    atomic_update.assert_not_called()


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"temp": 130}, "TEMPERATURE_OUT_OF_RANGE"),
        ({"temp": True}, "TEMPERATURE_INVALID"),
        ({"watts": -2}, "WATTS_OUT_OF_RANGE"),
        ({"watts": float("inf")}, "WATTS_OUT_OF_RANGE"),
        ({"temp": None}, "TEMPERATURE_REQUIRED"),
        ({"status": {"unsafe": "object"}}, "STATUS_INVALID"),
    ],
)
def test_ingest_rejects_invalid_measurements_without_writing(monkeypatch, overrides, expected_code):
    _configure_global_token(monkeypatch)
    db = _db()
    with patch.object(miner_service.state_manager, "load_db", return_value=db), patch.object(
        miner_service.state_manager, "atomic_update"
    ) as atomic_update:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(**overrides), f"Bearer {TOKEN}")
    assert exc.value.code == expected_code
    assert exc.value.status_code == 400
    atomic_update.assert_not_called()


def test_get_miner_telemetry_reads_existing_device_and_does_not_invent_values():
    db = _db()
    with patch.object(miner_service.state_manager, "load_db", return_value=db):
        assert miner_service.get_miner_telemetry(DEVICE_ID) is None
        db["devices"][DEVICE_ID]["telemetry"] = {"temperature_c": 68.5, "watts": None}
        assert miner_service.get_miner_telemetry(DEVICE_ID) == {
            "temperature_c": 68.5,
            "watts": None,
        }
        assert miner_service.get_miner_telemetry("MISSING") is None


def test_miner_api_route_calls_authenticated_ingestion_service():
    from flask import Flask
    from core.mcp_bridge_routes import register_mcp_bridge_routes

    app = Flask("miner-route-test")
    register_mcp_bridge_routes(app)
    response_record = {
        "device_id": DEVICE_ID,
        "health_status": "OK",
        "alerts": [],
        "last_seen": "2026-10-17T11:00:00Z",
    }
    with patch("core.miner_service.ingest_telemetry", return_value=response_record) as ingest:
        response = app.test_client().post(
            "/api/miner",
            json=_payload(),
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, **response_record}
    ingest.assert_called_once()


def test_miner_api_route_rejects_non_object_json():
    from flask import Flask
    from core.mcp_bridge_routes import register_mcp_bridge_routes

    app = Flask("miner-route-invalid-test")
    register_mcp_bridge_routes(app)
    response = app.test_client().post("/api/miner", data="[]", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON_OBJECT_REQUIRED"}


def test_miner_api_route_rejects_oversized_payload():
    from flask import Flask
    from core.mcp_bridge_routes import register_mcp_bridge_routes

    app = Flask("miner-route-large-body-test")
    register_mcp_bridge_routes(app)
    response = app.test_client().post(
        "/api/miner",
        data="x" * 8193,
        content_type="application/json",
    )
    assert response.status_code == 413
    assert response.get_json() == {"error": "PAYLOAD_TOO_LARGE"}


def test_mcp_bridge_lists_only_safe_miner_fields_and_is_read_only(monkeypatch):
    from flask import Flask
    from core.mcp_bridge_routes import register_mcp_bridge_routes

    app = Flask("mcp-miner-list-test")
    register_mcp_bridge_routes(app)
    monkeypatch.setenv("SLH_MCP_BRIDGE_TOKEN", TOKEN)
    monkeypatch.setenv("SLH_MCP_BRIDGE_PRINCIPAL_ID", "8789977826")
    device = {
        "device_id": DEVICE_ID,
        "owner_id": "8789977826",
        "type": "esp32",
        "status": "online",
        "mqtt_topics": {"telemetry": "slh/esp/test/telemetry"},
        "miner_enabled": True,
        "secret_field": "must not escape",
        "telemetry": {
            "temperature_c": 68.5,
            "watts": 3250.0,
            "last_seen": "2026-10-17T11:00:00Z",
            "secret": "must not escape",
        },
    }
    with patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
        "core.miner_service.list_registered_esp_devices", return_value={DEVICE_ID: device}
    ), patch("core.miner_service.device_role_enabled", return_value=True):
        response = app.test_client().get(
            "/internal/mcp/v1/miners",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 200
    result = response.get_json()
    assert result["count"] == 1
    assert result["devices"][0]["telemetry"]["temperature_c"] == 68.5
    assert "secret_field" not in result["devices"][0]
    assert "secret" not in result["devices"][0]["telemetry"]


def test_mcp_miner_bridge_requires_auth(monkeypatch):
    from flask import Flask
    from core.mcp_bridge_routes import register_mcp_bridge_routes

    app = Flask("mcp-miner-auth-test")
    register_mcp_bridge_routes(app)
    monkeypatch.setenv("SLH_MCP_BRIDGE_TOKEN", TOKEN)
    monkeypatch.setenv("SLH_MCP_BRIDGE_PRINCIPAL_ID", "8789977826")
    response = app.test_client().get("/internal/mcp/v1/miners")
    assert response.status_code == 401
    assert response.get_json() == {"error": "MCP_BRIDGE_AUTH_REQUIRED"}
