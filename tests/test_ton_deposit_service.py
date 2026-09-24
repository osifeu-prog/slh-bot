import unittest
from unittest.mock import patch

from core import ton_deposit_service


UID = "12345"
BOUND = "0:" + "22" * 32
TREASURY = "0:" + "33" * 32
TX = "abc123"


class TonDepositSettlementTests(unittest.TestCase):
    def setUp(self):
        self.db = {"users": {UID: {"wallet": {"credits": 0}}}}

        def atomic_update(fn):
            return fn(self.db)

        self.atomic_patch = patch.object(
            ton_deposit_service.state_manager,
            "atomic_update",
            side_effect=atomic_update,
        )
        self.load_patch = patch.object(
            ton_deposit_service.state_manager,
            "load_db",
            side_effect=lambda: self.db,
        )
        self.binding_patch = patch.object(
            ton_deposit_service,
            "get_ton_binding",
            return_value={"uid": UID, "address": BOUND, "network": "-239"},
        )
        self.tx_patch = patch.object(ton_deposit_service, "_find_ton_transaction")
        self.open_patch = patch.object(ton_deposit_service, "_deposits_open", return_value=True)
        self.settings_patch = patch.object(
            ton_deposit_service,
            "_settings",
            return_value=(TREASURY, 100),
        )
        self.atomic_patch.start()
        self.load_patch.start()
        self.binding_patch.start()
        self.tx_patch.start()
        self.open_patch.start()
        self.settings_patch.start()
        self.addCleanup(self.atomic_patch.stop)
        self.addCleanup(self.load_patch.stop)
        self.addCleanup(self.binding_patch.stop)
        self.addCleanup(self.tx_patch.stop)
        self.addCleanup(self.open_patch.stop)
        self.addCleanup(self.settings_patch.stop)

    def _tx(self, sender=BOUND, recipient=TREASURY, value_nano=1_000_000_000, memo="SLH12345"):
        return {
            "tx_hash": TX,
            "from": sender,
            "to": recipient,
            "amount_ton": value_nano / 1_000_000_000,
            "memo": memo,
            "observed": True,
        }

    def test_unsafe_rate_makes_effective_deposits_closed(self):
        self.settings_patch.stop()
        unsafe = patch.object(
            ton_deposit_service,
            "_settings",
            return_value=(TREASURY, 1000),
        )
        unsafe.start()
        self.addCleanup(unsafe.stop)
        self.assertFalse(ton_deposit_service.deposits_are_open())

    def test_wrong_sender_rejected(self):
        self.tx_patch.return_value = self._tx(sender="0:" + "44" * 32)
        with self.assertRaisesRegex(ValueError, "TON_TX_SENDER_NOT_BOUND_WALLET"):
            ton_deposit_service.settle_ton_deposit(UID, TX)

    def test_wrong_treasury_rejected(self):
        self.tx_patch.return_value = self._tx(recipient="0:" + "55" * 32)
        with self.assertRaisesRegex(ValueError, "TON_TX_RECIPIENT_NOT_TREASURY"):
            ton_deposit_service.settle_ton_deposit(UID, TX)

    def test_wrong_memo_rejected(self):
        self.tx_patch.return_value = self._tx(memo="SLH999")
        with self.assertRaisesRegex(ValueError, "TON_TX_MEMO_MISMATCH"):
            ton_deposit_service.settle_ton_deposit(UID, TX)

    def test_success_is_idempotent(self):
        self.tx_patch.return_value = self._tx()
        first = ton_deposit_service.settle_ton_deposit(UID, TX)
        second = ton_deposit_service.settle_ton_deposit(UID, TX)
        self.assertTrue(first["ok"])
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["ok"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(self.db["users"][UID]["wallet"]["credits"], 100)
        self.assertEqual(self.db["used_ton_txs"], [TX])

    def test_unsafe_rate_is_rejected_when_deposits_open(self):
        self.tx_patch.return_value = self._tx()
        self.settings_patch.stop()
        unsafe = patch.object(
            ton_deposit_service,
            "_settings",
            return_value=(TREASURY, 1000),
        )
        unsafe.start()
        self.addCleanup(unsafe.stop)
        with self.assertRaisesRegex(ValueError, "TON_RATE_NOT_SAFE"):
            ton_deposit_service.settle_ton_deposit(UID, TX)


if __name__ == "__main__":
    unittest.main()
