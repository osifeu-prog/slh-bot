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


def _registry():
    return {
        "devices": {
            DEVICE_ID: {
                "type": "esp32",
                "owner": "8789977826",
                "miner_enabled": True,
                "mqtt_topic": f"slh/esp/{DEVICE_ID}",
            }
        }
    }


def _configure_global_token(monkeypatch):
    monkeypatch.delenv("SLH_MINER_DEVICE_TOKENS_JSON", raising=False)
    monkeypatch.setenv("SLH_MINER_INGEST_TOKEN", TOKEN)


def test_ingest_saves_valid_telemetry_atomically_without_touching_user_ledger(monkeypatch):
    _configure_global_token(monkeypatch)
    db = {"users": {"8789977826": {"wallet": {"credits": 7}}}, "ledger": [{"id": "unchanged"}]}
    original_ledger = list(db["ledger"])
    original_user = dict(db["users"]["8789977826"])

    def apply(mutate):
        return mutate(db)

    with patch.object(miner_service.state_manager, "load_json", return_value=_registry()), patch.object(
        miner_service.state_manager, "atomic_update", side_effect=apply
    ) as atomic_update:
        saved = miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")

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
    assert db["miners"][DEVICE_ID] == saved
    assert db["ledger"] == original_ledger
    assert db["users"]["8789977826"] == original_user
    atomic_update.assert_called_once()


def test_ingest_derives_advisory_alerts_but_never_issues_hardware_commands(monkeypatch):
    _configure_global_token(monkeypatch)
    db = {"users": {}}
    with patch.object(miner_service.state_manager, "load_json", return_value=_registry()), patch.object(
        miner_service.state_manager, "atomic_update", side_effect=lambda mutate: mutate(db)
    ):
        saved = miner_service.ingest_telemetry(
            _payload(temp=86, watts=0),
            f"Bearer {TOKEN}",
        )

    assert saved["health_status"] == "ALERT"
    assert saved["alerts"] == ["TEMPERATURE_CRITICAL", "POWER_LOW_REVIEW"]
    assert "relay" not in saved
    assert "command" not in saved


def test_ingest_fails_closed_when_token_is_not_configured(monkeypatch):
    monkeypatch.delenv("SLH_MINER_INGEST_TOKEN", raising=False)
    monkeypatch.delenv("SLH_MINER_DEVICE_TOKENS_JSON", raising=False)

    with patch.object(miner_service.state_manager, "load_json") as load_registry:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")

    assert exc.value.code == "MINER_INGEST_NOT_CONFIGURED"
    assert exc.value.status_code == 503
    load_registry.assert_not_called()


def test_device_specific_token_is_required_when_token_map_is_configured(monkeypatch):
    monkeypatch.setenv("SLH_MINER_DEVICE_TOKENS_JSON", json.dumps({DEVICE_ID: "device-specific-token"}))
    monkeypatch.setenv("SLH_MINER_INGEST_TOKEN", TOKEN)

    with patch.object(miner_service.state_manager, "load_json", return_value=_registry()), patch.object(
        miner_service.state_manager, "atomic_update"
    ) as atomic_update:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")

    assert exc.value.code == "MINER_AUTH_INVALID"
    assert exc.value.status_code == 401
    atomic_update.assert_not_called()


def test_ingest_rejects_unregistered_device_before_state_write(monkeypatch):
    _configure_global_token(monkeypatch)
    with patch.object(miner_service.state_manager, "load_json", return_value={"devices": {}}), patch.object(
        miner_service.state_manager, "atomic_update"
    ) as atomic_update:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")

    assert exc.value.code == "MINER_DEVICE_NOT_REGISTERED"
    assert exc.value.status_code == 404
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
    with patch.object(miner_service.state_manager, "load_json", return_value=_registry()), patch.object(
        miner_service.state_manager, "atomic_update"
    ) as atomic_update:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(**overrides), f"Bearer {TOKEN}")

    assert exc.value.code == expected_code
    assert exc.value.status_code == 400
    atomic_update.assert_not_called()


def test_get_miner_telemetry_returns_none_instead_of_inventing_zero_values():
    with patch.object(miner_service.state_manager, "load_db", return_value={"users": {}, "miners": {}}):
        assert miner_service.get_miner_telemetry(DEVICE_ID) is None


def test_miner_api_route_calls_the_authenticated_ingestion_service():
    from flask import Flask
    from core.mcp_bridge_routes import register_mcp_bridge_routes

    app = Flask("miner-route-test")
    register_mcp_bridge_routes(app)
    client = app.test_client()
    response_record = {
        "device_id": DEVICE_ID,
        "health_status": "OK",
        "alerts": [],
        "last_seen": "2026-10-17T11:00:00Z",
    }

    with patch("core.miner_service.ingest_telemetry", return_value=response_record) as ingest:
        response = client.post(
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


def test_ingest_rejects_generic_esp32_without_explicit_miner_opt_in(monkeypatch):
    _configure_global_token(monkeypatch)
    registry = {"devices": {DEVICE_ID: {"type": "esp32", "owner": "8789977826"}}}
    with patch.object(miner_service.state_manager, "load_json", return_value=registry), patch.object(
        miner_service.state_manager, "atomic_update"
    ) as atomic_update:
        with pytest.raises(miner_service.MinerTelemetryError) as exc:
            miner_service.ingest_telemetry(_payload(), f"Bearer {TOKEN}")

    assert exc.value.code == "MINER_ROLE_NOT_ENABLED"
    assert exc.value.status_code == 403
    atomic_update.assert_not_called()



def test_device_specific_token_is_accepted_for_the_matching_registered_node(monkeypatch):
    monkeypatch.setenv("SLH_MINER_DEVICE_TOKENS_JSON", json.dumps({DEVICE_ID: "device-specific-token"}))
    monkeypatch.delenv("SLH_MINER_INGEST_TOKEN", raising=False)
    db = {"users": {}}

    with patch.object(miner_service.state_manager, "load_json", return_value=_registry()), patch.object(
        miner_service.state_manager, "atomic_update", side_effect=lambda mutate: mutate(db)
    ):
        saved = miner_service.ingest_telemetry(_payload(), "Bearer device-specific-token")

    assert saved["device_id"] == DEVICE_ID
    assert db["miners"][DEVICE_ID]["temperature_c"] == 68.5



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
