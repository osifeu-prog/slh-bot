"""Regression tests for the guarded internal Exchange opening control."""

from datetime import datetime, timedelta, timezone
import os
from unittest.mock import patch
import time

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
        "account_ledger_status": "PASS",
        "account_ledger_integrity": True,
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
        {"account_ledger_status": "BLOCKED"},
        {"account_ledger_integrity": False},
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


def test_opening_proof_requires_explicit_ledger_evidence():
    proof = _fresh_opening_proof()
    proof.pop("account_ledger_status")
    with pytest.raises(railway_control.RailwayControlError, match="EXCHANGE_OPENING_PROOF_INVALID"):
        _validator()(proof)

    proof = _fresh_opening_proof()
    proof.pop("account_ledger_integrity")
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
        "status": "DEPLOYMENT_SUCCESS",
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

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["configured"] == "1"
    assert payload["status"] == "DEPLOYMENT_SUCCESS"
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
    ) as deploy, patch.object(
        railway_control, "deployment_status", return_value={"status": "SUCCESS"}
    ) as deployment_status:
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
    assert result["status"] == "DEPLOYMENT_SUCCESS"
    assert result["configured"] == "1"
    assert result["deployment_id"] == "deployment-open"
    deployment_status.assert_called_once_with("deployment-open", prefer_account_token=True)


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
    ), patch.object(railway_control, "deploy", side_effect=fake_deploy) as deploy, patch.object(
        railway_control, "deployment_status", return_value={"status": "SUCCESS"}
    ):
        with pytest.raises(
            railway_control.RailwayControlError,
            match="EXCHANGE_GATE_OPEN_FAILED_ROLLED_BACK",
        ):
            railway_control.open_exchange_gate(proof)

    assert [call.args[1]["input"]["value"] for call in graphql.call_args_list] == ["1", "0"]
    assert deploy.call_count == 2



def test_open_gate_waits_for_terminal_success_before_returning():
    proof = _fresh_opening_proof()
    statuses = iter([
        {"configured": "0", "configured_open": False},
        {"configured": "1", "configured_open": True},
    ])
    deploy_states = iter([
        {"status": "BUILDING"},
        {"status": "DEPLOYING"},
        {"status": "SUCCESS"},
    ])

    with patch.object(
        railway_control, "exchange_gate_variable_status", side_effect=lambda: next(statuses)
    ), patch.object(
        railway_control, "graphql", return_value={"variableUpsert": True}
    ), patch.object(
        railway_control, "latest_github_commit", return_value="d" * 40
    ), patch.object(
        railway_control, "deploy", return_value={"id": "deployment-open"}
    ), patch.object(
        railway_control, "deployment_status", side_effect=lambda *_args, **_kwargs: next(deploy_states)
    ) as deployment_status, patch.object(
        time, "sleep", return_value=None
    ):
        result = railway_control.open_exchange_gate(proof)

    assert deployment_status.call_count == 3
    assert result["status"] == "DEPLOYMENT_SUCCESS"


def test_open_gate_rolls_back_and_verifies_closed_deployment_when_deploy_fails():
    proof = _fresh_opening_proof()
    statuses = iter([
        {"configured": "0", "configured_open": False},
        {"configured": "1", "configured_open": True},
        {"configured": "0", "configured_open": False},
    ])
    deploys = iter([
        {"id": "deployment-open"},
        {"id": "deployment-close"},
    ])
    deploy_states = iter([
        {"status": "FAILED"},
        {"status": "SUCCESS"},
    ])
    graphql_calls = []

    def fake_graphql(query, variables=None, *, prefer_account_token=False):
        graphql_calls.append(variables["input"]["value"])
        return {"variableUpsert": True}

    with patch.object(
        railway_control, "exchange_gate_variable_status", side_effect=lambda: next(statuses)
    ), patch.object(
        railway_control, "graphql", side_effect=fake_graphql
    ), patch.object(
        railway_control, "latest_github_commit", return_value="e" * 40
    ), patch.object(
        railway_control, "deploy", side_effect=lambda *_args, **_kwargs: next(deploys)
    ) as deploy, patch.object(
        railway_control, "deployment_status", side_effect=lambda *_args, **_kwargs: next(deploy_states)
    ), patch.object(
        time, "sleep", return_value=None
    ):
        with pytest.raises(
            railway_control.RailwayControlError,
            match="EXCHANGE_GATE_OPEN_FAILED_ROLLED_BACK",
        ):
            railway_control.open_exchange_gate(proof)

    assert graphql_calls == ["1", "0"]
    assert deploy.call_count == 2


def test_owner_private_text_phrase_routes_to_guarded_exchange_open_helper():
    from types import SimpleNamespace
    import handlers.exchange_handler as exchange_handler

    route = getattr(exchange_handler, "route_exchange_gate_text", None)
    assert callable(route), "owner-only Exchange typed-text route is missing"
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


def test_non_owner_cannot_request_exchange_gate_open_by_typed_text():
    from types import SimpleNamespace
    import handlers.exchange_handler as exchange_handler

    route = getattr(exchange_handler, "route_exchange_gate_text", None)
    assert callable(route), "owner-only Exchange typed-text route is missing"
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
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


def test_register_wires_only_the_allowlisted_typed_exchange_phrase_before_fallback():
    from types import SimpleNamespace
    import handlers.exchange_handler as exchange_handler

    class FakeBot:
        def __init__(self):
            self.registered = []
            self.replies = []

        def message_handler(self, *args, **kwargs):
            def decorator(fn):
                self.registered.append((kwargs, fn))
                return fn
            return decorator

        def __getattr__(self, name):
            if name.endswith("_handler"):
                return self.message_handler
            raise AttributeError(name)

        def reply_to(self, message, text, **kwargs):
            self.replies.append((message, text, kwargs))

    bot = FakeBot()
    exchange_handler.register(bot)
    entry = next(
        (
            (options, fn) for options, fn in bot.registered
            if fn.__name__ == "exchange_gate_text_cmd"
        ),
        None,
    )
    assert entry is not None, "exact Exchange typed-text handler is not registered"
    options, fn = entry
    predicate = options.get("func")
    assert callable(predicate), "typed-text handler needs an exact phrase predicate"

    allowed = SimpleNamespace(
        text="פתח מסחר פנימי אם בדיקת המוכנות הקנונית עוברת",
        from_user=SimpleNamespace(id=8789977826),
        chat=SimpleNamespace(type="private"),
    )
    unrelated = SimpleNamespace(
        text="פתח BNB",
        from_user=SimpleNamespace(id=8789977826),
        chat=SimpleNamespace(type="private"),
    )
    assert predicate(allowed) is True
    assert predicate(unrelated) is False

    with patch.object(
        exchange_handler,
        "_request_guarded_exchange_gate_open",
        return_value="GUARDED_RESULT",
    ) as open_gate:
        fn(allowed)

    open_gate.assert_called_once_with()
    assert bot.replies and bot.replies[-1][1] == "GUARDED_RESULT"

def test_guarded_opening_proof_copies_actual_ledger_check_into_validator():
    import handlers.exchange_handler as exchange_handler

    check = {
        "ok": True,
        "public_gate": "CLOSED",
        "verdict": "READY_TO_OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "account_ledger_status": "PASS",
        "account_ledger_integrity": True,
        "open_orders": 0,
        "test_seed_open": 0,
        "test_seed_trades": 0,
    }
    result = {
        "status": "DEPLOYMENT_SUCCESS",
        "commit": "a" * 40,
        "deployment_id": "deployment-open",
    }
    captured = {}

    def validate_before_mutation(proof):
        captured.update(proof)
        _validator()(proof)
        return result

    with patch.object(exchange_handler.state_manager, "load_db", return_value={}), patch(
        "core.system_checks.check_exchange", return_value=check
    ), patch(
        "core.railway_control.request_exchange_gate_open",
        side_effect=validate_before_mutation,
    ), patch.object(
        exchange_handler, "_wait_for_public_exchange_open", return_value={"verified": True}
    ), patch.object(
        exchange_handler, "_prepare_verified_exchange_broadcast_preview", return_value="PREVIEW"
    ):
        answer = exchange_handler._request_guarded_exchange_gate_open()

    assert captured["account_ledger_status"] == check["account_ledger_status"]
    assert captured["account_ledger_integrity"] is check["account_ledger_integrity"]
    assert captured["public_gate"] == check["public_gate"]
    assert captured["verdict"] == check["verdict"]
    assert answer.startswith("✅ EXCHANGE OPEN VERIFIED")


@pytest.mark.parametrize(
    "ledger_change",
    [
        {"account_ledger_status": "BLOCKED"},
        {"account_ledger_integrity": False},
    ],
)
def test_guarded_opening_rejects_nonpassing_ledger_before_request(ledger_change):
    import handlers.exchange_handler as exchange_handler

    check = {
        "ok": True,
        "public_gate": "CLOSED",
        "verdict": "READY_TO_OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "account_ledger_status": "PASS",
        "account_ledger_integrity": True,
        "open_orders": 0,
        "test_seed_open": 0,
        "test_seed_trades": 0,
    }
    check.update(ledger_change)

    with patch.object(exchange_handler.state_manager, "load_db", return_value={}), patch(
        "core.system_checks.check_exchange", return_value=check
    ), patch(
        "core.railway_control.request_exchange_gate_open"
    ) as open_gate:
        answer = exchange_handler._request_guarded_exchange_gate_open()

    open_gate.assert_not_called()
    assert "Exchange gate נשאר CLOSED" in answer

