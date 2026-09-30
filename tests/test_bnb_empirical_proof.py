"""Isolated BNB settlement proof harness.

This suite never uses the production DB, RPC, wallet, or BNB gate.
It exercises the existing authorities against a temporary state file and
deterministic verifier fixture.
"""

import json
from unittest.mock import patch

from eth_account import Account
from eth_account.messages import encode_defunct

from core import bnb_deposit_service, deposit_monitor, wallet_binding
import state_manager


def _isolated_db(tmp_path, uid="proof-user"):
    path = tmp_path / "db.json"
    path.write_text(
        json.dumps({
            "users": {uid: {"wallet": {"credits": 10.0}}},
            "ledger": [],
            "wallet_challenges": {},
            "wallet_bindings": {},
        }),
        encoding="utf-8",
    )
    return path


def _patch_db(path):
    return patch.multiple(
        state_manager,
        DB_FILE=str(path),
        _LOCK_PATH=str(path) + ".lock",
    )


def test_wallet_binding_contract_is_proven_in_isolated_state(tmp_path):
    path = _isolated_db(tmp_path)
    account = Account.create()
    uid = "proof-user"

    with _patch_db(path):
        challenge = wallet_binding.issue_challenge(uid, account.address)
        signed = Account.sign_message(
            encode_defunct(text=challenge["message"]),
            private_key=account.key,
        )
        binding = wallet_binding.verify_signature(
            uid, account.address, signed.signature.hex()
        )

        assert binding["uid"] == uid
        assert binding["address"].lower() == account.address.lower()

        stored = state_manager.load_db()
        assert stored["wallet_bindings"][account.address.lower()]["uid"] == uid
        assert stored["wallet_challenges"]["bsc:" + uid]["consumed"] is True


def test_settlement_idempotency_and_reconciliation_are_proven_in_isolated_state(
    tmp_path,
):
    path = _isolated_db(tmp_path)
    uid = "proof-user"
    bound = "0x1111111111111111111111111111111111111111"
    tx_hash = "0x" + "ab" * 32

    verified = {
        "ok": True,
        "from": bound,
        "to": "0x2222222222222222222222222222222222222222",
        "amount_bnb": 2.5,
        "amount_wei": 2500000000000000000,
        "block": 123,
        "confirmations": 15,
        "tx_hash": tx_hash,
    }

    with _patch_db(path), patch(
        "core.bnb_deposit_service.bnb_deposits_open",
        return_value=True,
    ), patch(
        "core.bnb_deposit_service.get_binding",
        return_value={"uid": uid, "chain": "bsc", "address": bound},
    ), patch(
        "core.bnb_deposit_service.verify_bnb_deposit",
        return_value=verified,
    ):
        first = bnb_deposit_service.settle_bnb_deposit(uid, tx_hash)
        second = bnb_deposit_service.settle_bnb_deposit(uid, tx_hash)
        db = state_manager.load_db()

    assert first["amount_wei"] == 2500000000000000000
    assert first["credits"] == 2500.0
    assert second["idempotent"] is True
    assert second["balance_after"] == 2510.0

    user = db["users"][uid]
    assert user["wallet"]["credits"] == 2510.0

    matching = [
        e for e in db["ledger"]
        if e.get("meta", {}).get("idempotency_key")
        == "bnb:deposit:" + tx_hash.lower()
    ]
    assert len(matching) == 1
    assert matching[0]["before"] == 10.0
    assert matching[0]["after"] == 2510.0
    assert matching[0]["amount"] == 2500.0
    assert matching[0]["meta"]["bnb_amount_wei"] == 2500000000000000000


def test_bnb_tx_verification_contract_rejects_unverified_fixture():
    with patch(
        "core.deposit_monitor.get_bsc_config",
        return_value={
            "rpc": "https://example.invalid",
            "treasury_wallet": "0x2222222222222222222222222222222222222222",
            "confirmations": 15,
        },
    ), patch(
        "core.deposit_monitor.Web3"
    ) as web3_cls:
        web3 = web3_cls.return_value
        web3.eth.get_transaction.side_effect = RuntimeError("fixture unavailable")
        result = deposit_monitor.verify_bnb_deposit("0x" + "cd" * 32)

    assert result["ok"] is False
    assert "fixture unavailable" in result["error"]
