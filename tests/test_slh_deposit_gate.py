import os
from pathlib import Path

from core import slh_deposit_service as slh


TOKEN = "0x8888888888888888888888888888888888888888"
TREASURY = "0x9999999999999999999999999999999999999999"


def _mock_readiness(monkeypatch, *, ready=True, reasons=None, config=None, baseline=True):
    monkeypatch.setattr(
        slh,
        "bnb_readiness",
        lambda _db=None: {"ready": ready, "reasons": reasons or []},
    )
    monkeypatch.setattr(
        slh,
        "_config",
        lambda: config or {"token_contract": TOKEN, "treasury_wallet": TREASURY},
    )
    if baseline:
        monkeypatch.setattr(slh, "_configured_baseline", lambda: 123)
    else:
        monkeypatch.setattr(
            slh,
            "_configured_baseline",
            lambda: (_ for _ in ()).throw(ValueError("SLH_SUPPLY_BASELINE_NOT_CONFIGURED")),
        )


def test_slh_gate_defaults_closed_even_if_bnb_flag_is_open(monkeypatch):
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")
    monkeypatch.delenv("SLH_DEPOSITS_OPEN", raising=False)
    monkeypatch.delenv("SLH_DEPOSITS_CANARY_UID", raising=False)
    _mock_readiness(monkeypatch)

    status = slh.slh_deposit_readiness()

    assert status["ready"] is True
    assert status["flag_open"] is False
    assert status["effective_open"] is False
    assert slh.slh_settlement_allowed("501") is False


def test_slh_public_gate_is_independent_of_bnb_public_flag(monkeypatch):
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")
    monkeypatch.setenv("SLH_DEPOSITS_OPEN", "1")
    monkeypatch.delenv("SLH_DEPOSITS_CANARY_UID", raising=False)
    _mock_readiness(monkeypatch)

    status = slh.slh_deposit_readiness()

    assert status["ready"] is True
    assert status["effective_open"] is True
    assert slh.slh_settlement_allowed("501") is True


def test_slh_gate_fails_closed_if_bsc_infrastructure_is_not_ready(monkeypatch):
    monkeypatch.setenv("SLH_DEPOSITS_OPEN", "1")
    _mock_readiness(monkeypatch, ready=False, reasons=["BSC_RPC_MISSING"])

    status = slh.slh_deposit_readiness()

    assert status["ready"] is False
    assert status["effective_open"] is False
    assert "BSC_RPC_MISSING" in status["reasons"]
    assert slh.slh_settlement_allowed("501") is False


def test_slh_gate_requires_the_existing_supply_baseline(monkeypatch):
    monkeypatch.setenv("SLH_DEPOSITS_OPEN", "1")
    _mock_readiness(monkeypatch, baseline=False)

    status = slh.slh_deposit_readiness()

    assert status["ready"] is False
    assert "SLH_SUPPLY_BASELINE_NOT_CONFIGURED" in status["reasons"]
    assert slh.slh_settlement_allowed("501") is False


def test_slh_canary_is_independent_and_uid_scoped(monkeypatch):
    monkeypatch.delenv("SLH_DEPOSITS_OPEN", raising=False)
    monkeypatch.setenv("SLH_DEPOSITS_CANARY_UID", "8789977826")
    _mock_readiness(monkeypatch)

    assert slh.slh_settlement_allowed("8789977826") is True
    assert slh.slh_settlement_allowed("501") is False
    assert slh.slh_deposit_readiness()["canary_configured"] is True


def test_slh_gate_rejects_invalid_contract_or_treasury(monkeypatch):
    monkeypatch.setenv("SLH_DEPOSITS_OPEN", "1")
    _mock_readiness(
        monkeypatch,
        config={"token_contract": "not-an-address", "treasury_wallet": TREASURY},
    )

    status = slh.slh_deposit_readiness()

    assert status["ready"] is False
    assert "SLH_TOKEN_CONTRACT_INVALID" in status["reasons"]
    assert slh.slh_settlement_allowed("501") is False


def test_slh_settlement_entrypoints_and_ui_do_not_reuse_bnb_settlement_gate():
    service = Path("core/slh_deposit_service.py").read_text(encoding="utf-8")
    handler = Path("handlers/slh_deposit_handler.py").read_text(encoding="utf-8")
    webapp = Path("webapp.py").read_text(encoding="utf-8")

    assert "if not slh_settlement_allowed(uid):" in service
    assert "slh_settlement_allowed(msg.from_user.id)" in handler
    assert "slh_settlement_allowed(uid, db)" in webapp
    assert "slh_deposit_allowed = (deposits_open or bool(bnb_settlement_allowed(uid, db)))" not in webapp
    assert "from core.bnb_gate import CLOSED_MESSAGE, bnb_settlement_allowed" not in handler
