"""Regression tests for the guarded internal Exchange opening control."""

from datetime import datetime, timedelta, timezone
import os
from unittest.mock import patch

import pytest

import core.railway_control as railway_control
import webapp


def _fresh_opening_proof(now=None):
    now = now or datetime.now(timezone.utc)
    return {
        "status": "PASS",
        "checked_at": (now - timedelta(seconds=10)).isoformat(),
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


def _validator():
    validator = getattr(railway_control, "validate_exchange_opening_proof", None)
    assert callable(validator), "guarded Exchange opening proof validator is missing"
    return validator


def test_fresh_canonical_opening_proof_is_accepted():
    now = datetime.now(timezone.utc)

    result = _validator()(_fresh_opening_proof(now), now=now)

    assert result["public_gate"] == "CLOSED"
    assert result["verdict"] == "READY_TO_OPEN"
    assert result["status"] == "PASS"


@pytest.mark.parametrize(
    "change",
    [
        {"public_gate": "OPEN"},
        {"verdict": "BLOCKED"},
        {"public_ready": False},
        {"order_book_integrity": False},
        {"trade_integrity": False},
        {"money_invariants": False},
        {"open_orders": 1},
        {"test_seed_open": 1},
        {"test_seed_trades": 1},
        {"status": "BLOCKED"},
    ],
)
def test_opening_proof_rejects_non_green_or_non_launch_clean_state(change):
    proof = _fresh_opening_proof()
    proof.update(change)

    with pytest.raises(railway_control.RailwayControlError, match="EXCHANGE_OPENING_PROOF_INVALID"):
        _validator()(proof)


def test_opening_proof_rejects_stale_and_future_timestamps():
    now = datetime.now(timezone.utc)
    stale = _fresh_opening_proof(now)
    stale["checked_at"] = (now - timedelta(seconds=121)).isoformat()
    future = _fresh_opening_proof(now)
    future["checked_at"] = (now + timedelta(seconds=5)).isoformat()

    with pytest.raises(railway_control.RailwayControlError, match="EXCHANGE_OPENING_PROOF_INVALID"):
        _validator()(stale, now=now)
    with pytest.raises(railway_control.RailwayControlError, match="EXCHANGE_OPENING_PROOF_INVALID"):
        _validator()(future, now=now)


def test_opening_proof_requires_timezone_aware_timestamp():
    proof = _fresh_opening_proof()
    proof["checked_at"] = "2026-10-12T00:00:00"

    with pytest.raises(railway_control.RailwayControlError, match="EXCHANGE_OPENING_PROOF_INVALID"):
        _validator()(proof)


def test_internal_exchange_gate_endpoint_accepts_only_authenticated_fresh_opening_proof():
    proof = _fresh_opening_proof()
    result = {
        "status": "DEPLOY_TRIGGERED",
        "previous": "0",
        "configured": "1",
        "commit": "a" * 40,
        "deployment_id": "deployment-open",
        "service": "slh-cloud-bot",
        "environment": "production",
        "proof_checked_at": proof["checked_at"],
    }

    with patch.dict(os.environ, {"SLH_MCP_BRIDGE_TOKEN": "bridge-test-secret"}), patch(
        "core.railway_control.open_exchange_gate", return_value=result
    ) as open_gate:
        response = webapp.app.test_client().post(
            "/api/internal/exchange-gate",
            json={"action": "open", "proof": proof},
            headers={"Authorization": "Bearer bridge-test-secret"},
        )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["configured"] == "1"
    assert payload["status"] == "DEPLOY_TRIGGERED"
    assert payload["deployment_id"] == "deployment-open"
    open_gate.assert_called_once_with(proof)


def test_internal_exchange_gate_open_rejects_bad_proof_before_railway_mutation():
    proof = _fresh_opening_proof()
    proof["money_invariants"] = False

    with patch.dict(os.environ, {"SLH_MCP_BRIDGE_TOKEN": "bridge-test-secret"}), patch(
        "core.railway_control.graphql"
    ) as graphql:
        response = webapp.app.test_client().post(
            "/api/internal/exchange-gate",
            json={"action": "open", "proof": proof},
            headers={"Authorization": "Bearer bridge-test-secret"},
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "EXCHANGE_OPENING_PROOF_INVALID"
    graphql.assert_not_called()


def test_open_gate_sets_only_allowlisted_variable_and_deploys_fixed_production_target():
    proof = _fresh_opening_proof()
    statuses = iter([
        {"configured": "0", "configured_open": False},
        {"configured": "1", "configured_open": True},
    ])

    with patch.object(railway_control, "exchange_gate_variable_status", side_effect=lambda: next(statuses)), patch.object(
        railway_control, "graphql", return_value={"variableUpsert": True}
    ) as graphql, patch.object(
        railway_control, "latest_github_commit", return_value="b" * 40
    ), patch.object(
        railway_control, "deploy", return_value={"id": "deployment-open"}
    ) as deploy:
        result = railway_control.open_exchange_gate(proof)

    mutation = graphql.call_args.args[0]
    variables = graphql.call_args.args[1]
    assert "variableUpsert" in mutation
    assert variables["input"]["name"] == "SLH_EXCHANGE_PUBLIC_OPEN"
    assert variables["input"]["value"] == "1"
    assert variables["input"]["skipDeploys"] is True
    deploy.assert_called_once_with(
        railway_control.SLH_BOT_SERVICE_ID,
        railway_control.SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
        "b" * 40,
        prefer_account_token=True,
    )
    assert result["status"] == "DEPLOY_TRIGGERED"
    assert result["configured"] == "1"
    assert result["deployment_id"] == "deployment-open"


def test_open_gate_refuses_when_current_gate_is_not_closed_without_mutating_railway():
    proof = _fresh_opening_proof()

    with patch.object(
        railway_control, "exchange_gate_variable_status",
        return_value={"configured": "1", "configured_open": True},
    ), patch.object(railway_control, "graphql") as graphql, patch.object(
        railway_control, "deploy"
    ) as deploy:
        with pytest.raises(railway_control.RailwayControlError, match="EXCHANGE_GATE_NOT_CLOSED"):
            railway_control.open_exchange_gate(proof)

    graphql.assert_not_called()
    deploy.assert_not_called()



def test_owner_private_voice_phrase_routes_to_guarded_exchange_open_helper():
    from types import SimpleNamespace
    import handlers.exchange_handler as exchange_handler

    route = getattr(exchange_handler, "route_exchange_gate_voice", None)
    assert callable(route), "owner-only Exchange gate voice route is missing"
    bot = object()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=8789977826),
        chat=SimpleNamespace(type="private"),
    )

    with patch.object(
        exchange_handler,
        "_request_guarded_exchange_gate_open",
        return_value="OPENING_REQUEST_ACCEPTED",
    ) as open_gate:
        answer = route(
            bot,
            message,
            "פתח מסחר פנימי אם בדיקת המוכנות הקנונית עוברת",
        )

    assert answer == "OPENING_REQUEST_ACCEPTED"
    open_gate.assert_called_once_with()


def test_non_owner_cannot_request_exchange_gate_open_by_voice():
    from types import SimpleNamespace
    import handlers.exchange_handler as exchange_handler

    route = getattr(exchange_handler, "route_exchange_gate_voice", None)
    assert callable(route), "owner-only Exchange gate voice route is missing"
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=224223270),
        chat=SimpleNamespace(type="private"),
    )

    with patch.object(exchange_handler, "_request_guarded_exchange_gate_open") as open_gate:
        answer = route(
            object(),
            message,
            "פתח מסחר פנימי אם בדיקת המוכנות הקנונית עוברת",
        )

    assert "OWNER" in answer
    open_gate.assert_not_called()


def test_generic_voice_mutation_does_not_match_exchange_gate_open_route():
    from types import SimpleNamespace
    import handlers.exchange_handler as exchange_handler

    route = getattr(exchange_handler, "route_exchange_gate_voice", None)
    assert callable(route), "owner-only Exchange gate voice route is missing"
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=8789977826),
        chat=SimpleNamespace(type="private"),
    )

    with patch.object(exchange_handler, "_request_guarded_exchange_gate_open") as open_gate:
        answer = route(object(), message, "פתח BNB")

    assert answer is None
    open_gate.assert_not_called()



def test_open_gate_restores_closed_configuration_if_deployment_fails():
    proof = _fresh_opening_proof()
    statuses = iter([
        {"configured": "0", "configured_open": False},
        {"configured": "1", "configured_open": True},
        {"configured": "0", "configured_open": False},
    ])
    graphql_results = iter([
        {"variableUpsert": True},
        {"variableUpsert": True},
    ])
    deploy_results = iter([
        railway_control.RailwayControlError("DEPLOY_REQUEST_FAILED"),
        {"id": "deployment-close-reconcile"},
    ])

    def fake_graphql(query, variables=None, *, prefer_account_token=False):
        assert "variableUpsert" in query
        return next(graphql_results)

    def fake_deploy(*args, **kwargs):
        value = next(deploy_results)
        if isinstance(value, Exception):
            raise value
        return value

    with patch.object(
        railway_control,
        "exchange_gate_variable_status",
        side_effect=lambda: next(statuses),
    ), patch.object(railway_control, "graphql", side_effect=fake_graphql) as graphql, patch.object(
        railway_control, "latest_github_commit", return_value="c" * 40
    ), patch.object(railway_control, "deploy", side_effect=fake_deploy) as deploy:
        with pytest.raises(
            railway_control.RailwayControlError,
            match="EXCHANGE_GATE_OPEN_FAILED_ROLLED_BACK",
        ):
            railway_control.open_exchange_gate(proof)

    assert [call.args[1]["input"]["value"] for call in graphql.call_args_list] == ["1", "0"]
    assert deploy.call_count == 2
