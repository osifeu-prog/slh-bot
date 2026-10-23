from unittest.mock import patch

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



def test_release_readiness_blocks_clean_orderbook_when_accounting_audit_is_blocked(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    monkeypatch.setenv("BOT_TOKEN", "test-token")

    import core.system_checks as checks
    from core.release_readiness import _exchange_check

    monkeypatch.setattr(checks, "check_exchange", lambda: {
        "ok": False,
        "verdict": "BLOCKED",
        "public_gate": "CLOSED",
        "public_ready": False,
        "open_orders": 0,
        "recent_trades": 0,
        "test_seed_trades": 0,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "account_ledger_integrity": False,
        "account_ledger_status": "BLOCKED",
        "account_ledger_blockers": ["ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY"],
    })

    check = _exchange_check()

    assert check["status"] == "BLOCKED"
    assert "account_ledger=BLOCKED" in check["detail"]


def test_exchange_ready_but_closed_gate_is_not_reported_green(monkeypatch):
    import core.system_checks as checks
    from core.release_readiness import _exchange_check

    monkeypatch.setattr(
        checks,
        "check_exchange",
        lambda: {
            "ok": True,
            "verdict": "READY_TO_OPEN",
            "public_gate": "CLOSED",
            "public_ready": True,
            "open_orders": 0,
            "recent_trades": 0,
            "test_seed_trades": 0,
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": True,
            "account_ledger_integrity": True,
            "account_ledger_status": "PASS",
        },
    )

    result = _exchange_check()

    assert result["status"] == "DEGRADED"
    assert "public gate=CLOSED" in result["detail"]
    assert "not public-open" in result["detail"]


def test_public_exchange_gate_open_is_blocked_even_when_checks_pass(monkeypatch):
    import core.system_checks as checks
    from core.release_readiness import _exchange_check

    monkeypatch.setattr(
        checks,
        "check_exchange",
        lambda: {
            "ok": True,
            "verdict": "OPEN",
            "public_gate": "OPEN",
            "public_ready": True,
            "open_orders": 0,
            "recent_trades": 4,
            "test_seed_trades": 0,
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": True,
            "account_ledger_integrity": True,
            "account_ledger_status": "PASS",
        },
    )

    result = _exchange_check()

    assert result["status"] == "BLOCKED"
    assert "policy requires public gate=CLOSED" in result["detail"]
    assert "public trading is not authorized" in result["detail"]


def test_external_gate_check_reuses_caller_snapshot_for_ton_and_bnb(monkeypatch):
    import core.bnb_gate as bnb_gate
    import core.ton_deposit_service as ton_service
    import core.release_readiness as readiness

    monkeypatch.setenv("TON_DEPOSITS_OPEN", "1")
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")
    db = {
        "users": {},
        "ledger": [],
        "transactions": {},
        "ton_settings": {"wallet": "EQ-test", "credits_per_ton": 100},
        "bsc_settings": {"bnb_deposits_override": "auto"},
    }
    observed = []

    def ton_readiness(snapshot=None):
        observed.append(("ton", snapshot))
        return {"effective_open": True}

    def bnb_readiness(snapshot=None):
        observed.append(("bnb_readiness", snapshot))
        return {"flag_open": False, "effective_open": False, "ready": False}

    def bnb_deposits_open(snapshot=None):
        observed.append(("bnb_deposits_open", snapshot))
        return False

    def bnb_opening_evidence(snapshot=None):
        observed.append(("bnb_opening_evidence", snapshot))
        return {"ready_to_open": False}

    monkeypatch.setattr(ton_service, "ton_readiness", ton_readiness)
    monkeypatch.setattr(bnb_gate, "bnb_readiness", bnb_readiness)
    monkeypatch.setattr(bnb_gate, "bnb_deposits_open", bnb_deposits_open)
    monkeypatch.setattr(bnb_gate, "bnb_opening_evidence", bnb_opening_evidence)

    with patch("state_manager.load_db", side_effect=AssertionError("unexpected DB reload")):
        result = readiness._external_gate_check(db)

    assert result["status"] == "DEGRADED"
    assert {name for name, _snapshot in observed} == {
        "ton", "bnb_readiness", "bnb_deposits_open", "bnb_opening_evidence"
    }
    assert all(snapshot is db for _name, snapshot in observed)


def test_payments_check_reuses_caller_snapshot(monkeypatch):
    import core.release_readiness as readiness
    import core.revenue_ledger as revenue_ledger

    db = {"stars_revenue_ledger": []}
    observed = []

    def summary(snapshot=None):
        observed.append(snapshot)
        return {"events": 0, "totals": {}}

    monkeypatch.setattr(revenue_ledger, "summary", summary)
    result = readiness._payments_check(db)

    assert result["status"] == "GREEN"
    assert observed == [db]
