"""Regression tests for automatic post-deploy Exchange runtime verification."""

import json
import time
from unittest.mock import Mock, patch

import handlers.exchange_handler as exchange


def _public_payload(
    *,
    system_status="ONLINE",
    ok=True,
    gate="OPEN",
    readiness=True,
    verdict="OPEN",
):
    return {
        "ok": ok,
        "system": {"status": system_status, "updated_at": time.time()},
        "exchange": {
            "gate": gate,
            "readiness": readiness,
            "verdict": verdict,
        },
    }


def _green_public_result():
    return {
        "verified": True,
        "gate": "OPEN",
        "readiness": True,
        "verdict": "OPEN",
        "updated_at": time.time(),
        "detail": "canonical public runtime proof passed",
    }


def _open_check():
    return {
        "ok": True,
        "public_gate": "OPEN",
        "verdict": "OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
    }


def _ready_to_open_check():
    return {
        "ok": True,
        "public_gate": "CLOSED",
        "verdict": "READY_TO_OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "open_orders": 0,
        "test_seed_open": 0,
        "test_seed_trades": 0,
    }


def test_fetch_public_exchange_status_accepts_live_canonical_open_payload():
    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps(_public_payload()).encode("utf-8")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    with patch.object(exchange.urllib.request, "urlopen", return_value=response) as urlopen:
        result = exchange._fetch_public_exchange_status()

    assert result["verified"] is True
    assert result["gate"] == "OPEN"
    assert result["verdict"] == "OPEN"
    assert result["readiness"] is True
    request = urlopen.call_args.args[0]
    assert request.full_url == exchange.EXCHANGE_PUBLIC_STATUS_URL
    assert request.get_header("Cache-control") == "no-cache"
    assert urlopen.call_args.kwargs["timeout"] <= 5


def test_fetch_public_exchange_status_fails_closed_for_non_green_runtime_payloads():
    cases = [
        _public_payload(system_status="OFFLINE"),
        _public_payload(ok=False),
        _public_payload(gate="CLOSED", readiness=False, verdict="BLOCKED"),
        _public_payload(gate="OPEN", readiness=False, verdict="OPEN"),
        _public_payload(gate="OPEN", readiness=True, verdict="READY_TO_OPEN"),
        {**_public_payload(), "system": {"status": "ONLINE", "updated_at": time.time() - 121}},
        {**_public_payload(), "system": {"status": "ONLINE", "updated_at": time.time() + 10}},
    ]

    for payload in cases:
        response = Mock()
        response.status = 200
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(exchange.urllib.request, "urlopen", return_value=response):
            result = exchange._fetch_public_exchange_status()
        assert result["verified"] is False, payload


def test_fetch_public_exchange_status_fails_closed_on_http_error_or_invalid_json():
    with patch.object(
        exchange.urllib.request,
        "urlopen",
        side_effect=TimeoutError("probe timed out"),
    ):
        result = exchange._fetch_public_exchange_status()
    assert result["verified"] is False
    assert result["gate"] == "UNKNOWN"

    response = Mock()
    response.status = 200
    response.read.return_value = b"not-json"
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    with patch.object(exchange.urllib.request, "urlopen", return_value=response):
        result = exchange._fetch_public_exchange_status()
    assert result["verified"] is False


def test_wait_for_public_exchange_open_retries_a_temporary_closed_snapshot():
    blocked = {
        "verified": False,
        "gate": "CLOSED",
        "readiness": False,
        "verdict": "BLOCKED",
        "updated_at": None,
        "detail": "old runtime is still serving",
    }
    with patch.object(
        exchange,
        "_fetch_public_exchange_status",
        side_effect=[blocked, _green_public_result()],
    ) as probe, patch.object(exchange.time, "sleep") as sleep:
        result = exchange._wait_for_public_exchange_open(attempts=3, delay_seconds=0.1)

    assert result["verified"] is True
    assert probe.call_count == 2
    sleep.assert_called_once_with(0.1)


def test_existing_open_gate_auto_verifies_runtime_and_prepares_preview_only(monkeypatch):
    monkeypatch.setattr(exchange.state_manager, "load_db", lambda: {})
    with patch("core.system_checks.check_exchange", return_value=_open_check()), patch(
        "core.railway_control.control_plane_exchange_gate_status",
        return_value={"configured": "1"},
    ), patch.object(
        exchange, "_wait_for_public_exchange_open", return_value=_green_public_result()
    ), patch(
        "handlers.broadcast_handler.prepare_exchange_broadcast",
        return_value={
            "status": "PREPARED",
            "target_count": 123,
            "expires_at": "2026-10-12T02:18:00+00:00",
            "audience_scope": "all",
            "requires_duplicate_ack": False,
        },
    ) as prepare:
        result = exchange._request_guarded_exchange_gate_open()

    assert "OPEN VERIFIED" in result
    assert "123" in result
    assert "תצוגה מקדימה בלבד" in result
    assert "לא נשלחה הודעה לאף משתמש" in result
    assert "אשר ושלח ברודקאסט למסחר פנימי" in result
    assert "🟢 SLH OS — המסחר הפנימי פתוח" in result
    prepare.assert_called_once()


def test_successful_deployment_without_live_open_proof_never_prepares_or_announces(monkeypatch):
    monkeypatch.setattr(exchange.state_manager, "load_db", lambda: {})
    with patch(
        "core.system_checks.check_exchange", return_value=_ready_to_open_check()
    ), patch(
        "core.railway_control.request_exchange_gate_open",
        return_value={
            "status": "DEPLOYMENT_SUCCESS",
            "configured": "1",
            "commit": "e" * 40,
            "deployment_id": "deploy-open",
        },
    ), patch.object(
        exchange,
        "_wait_for_public_exchange_open",
        return_value={
            "verified": False,
            "gate": "CLOSED",
            "readiness": False,
            "verdict": "BLOCKED",
            "updated_at": None,
            "detail": "live endpoint did not confirm OPEN",
        },
    ), patch(
        "handlers.broadcast_handler.prepare_exchange_broadcast"
    ) as prepare:
        result = exchange._request_guarded_exchange_gate_open()

    assert "DEPLOYMENT SUCCESS" in result
    assert "RUNTIME NOT VERIFIED" in result
    assert "do not announce" in result.lower()
    assert "OPEN VERIFIED" not in result
    assert "מסחר פנימי פתוח" not in result
    prepare.assert_not_called()


def test_ready_to_open_gate_prepares_preview_only_after_live_runtime_verification(monkeypatch):
    monkeypatch.setattr(exchange.state_manager, "load_db", lambda: {})
    with patch(
        "core.system_checks.check_exchange", return_value=_ready_to_open_check()
    ), patch(
        "core.railway_control.request_exchange_gate_open",
        return_value={
            "status": "DEPLOYMENT_SUCCESS",
            "configured": "1",
            "commit": "e" * 40,
            "deployment_id": "deploy-open",
        },
    ), patch.object(
        exchange, "_wait_for_public_exchange_open", return_value=_green_public_result()
    ), patch(
        "handlers.broadcast_handler.prepare_exchange_broadcast",
        return_value={
            "status": "PREPARED",
            "target_count": 45,
            "expires_at": "2026-10-12T02:18:00+00:00",
            "audience_scope": "all",
            "requires_duplicate_ack": False,
        },
    ) as prepare:
        result = exchange._request_guarded_exchange_gate_open()

    assert "OPEN VERIFIED" in result
    assert "תצוגה מקדימה בלבד" in result
    assert "45" in result
    assert "לא נשלחה הודעה לאף משתמש" in result
    prepare.assert_called_once()


def test_already_open_runtime_not_canonical_never_prepares_preview(monkeypatch):
    monkeypatch.setattr(exchange.state_manager, "load_db", lambda: {})
    with patch("core.system_checks.check_exchange", return_value=_open_check()), patch(
        "core.railway_control.control_plane_exchange_gate_status",
        return_value={"configured": "0"},
    ), patch.object(
        exchange, "_wait_for_public_exchange_open"
    ) as probe, patch(
        "handlers.broadcast_handler.prepare_exchange_broadcast"
    ) as prepare:
        result = exchange._request_guarded_exchange_gate_open()

    assert "NOT VERIFIED" in result
    assert "do not announce" in result.lower()
    probe.assert_not_called()
    prepare.assert_not_called()
