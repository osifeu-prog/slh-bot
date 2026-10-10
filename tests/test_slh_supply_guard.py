"""Regression tests for the fail-closed on-chain SLH supply invariant."""

import os
import unittest
from unittest import mock

from core.slh_supply_guard import assert_supply_unchanged
from core.slh_deposit_service import verify_slh_deposit


TOKEN = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
TREASURY = "0x693db6c817083818696a7228aebfbd0cd3371f02"
BASELINE_RAW = 111186328000000000000000  # Test fixture only; production must set verified baseline.


class _Call:
    def __init__(self, value):
        self.value = value

    def call(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class _ContractFunctions:
    def __init__(self, total_supply):
        self._total_supply = total_supply

    def totalSupply(self):
        return _Call(self._total_supply)


class _Contract:
    def __init__(self, total_supply):
        self.functions = _ContractFunctions(total_supply)


class _Eth:
    def __init__(self, total_supply):
        self._total_supply = total_supply
        self.contract_calls = []

    def contract(self, *, address, abi):
        self.contract_calls.append((address, abi))
        return _Contract(self._total_supply)


class _Web3:
    def __init__(self, total_supply):
        self.eth = _Eth(total_supply)


class SlhSupplyGuardTests(unittest.TestCase):
    def setUp(self):
        self.clean_env = mock.patch.dict(os.environ, {}, clear=False)
        self.clean_env.start()
        os.environ.pop("SLH_SUPPLY_BASELINE_RAW", None)

    def tearDown(self):
        self.clean_env.stop()

    def test_accepts_exact_supply_when_explicit_baseline_matches(self):
        result = assert_supply_unchanged(
            _Web3(BASELINE_RAW), TOKEN, baseline_raw=BASELINE_RAW
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["total_supply_raw"], BASELINE_RAW)
        self.assertEqual(result["baseline_raw"], BASELINE_RAW)

    def test_fails_closed_when_total_supply_is_higher_than_baseline(self):
        with self.assertRaisesRegex(ValueError, "^SLH_SUPPLY_MISMATCH$"):
            assert_supply_unchanged(
                _Web3(BASELINE_RAW + 1), TOKEN, baseline_raw=BASELINE_RAW
            )

    def test_fails_closed_when_total_supply_is_lower_than_baseline(self):
        with self.assertRaisesRegex(ValueError, "^SLH_SUPPLY_MISMATCH$"):
            assert_supply_unchanged(
                _Web3(BASELINE_RAW - 1), TOKEN, baseline_raw=BASELINE_RAW
            )

    def test_supports_explicit_environment_baseline_override(self):
        override = "123456789"
        os.environ["SLH_SUPPLY_BASELINE_RAW"] = override
        result = assert_supply_unchanged(_Web3(int(override)), TOKEN)
        self.assertEqual(result["baseline_raw"], int(override))

    def test_missing_environment_baseline_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "^SLH_SUPPLY_BASELINE_NOT_CONFIGURED$"):
            assert_supply_unchanged(_Web3(BASELINE_RAW), TOKEN)

    def test_invalid_environment_baseline_fails_closed(self):
        os.environ["SLH_SUPPLY_BASELINE_RAW"] = "not-an-integer"
        with self.assertRaisesRegex(ValueError, "^SLH_SUPPLY_BASELINE_INVALID$"):
            assert_supply_unchanged(_Web3(BASELINE_RAW), TOKEN)

    def test_unavailable_total_supply_fails_closed(self):
        web3 = _Web3(RuntimeError("rpc unavailable"))
        with self.assertRaisesRegex(ValueError, "^SLH_SUPPLY_UNAVAILABLE$"):
            assert_supply_unchanged(web3, TOKEN, baseline_raw=BASELINE_RAW)


class SlhDepositSupplyIntegrationTests(unittest.TestCase):
    @mock.patch("core.slh_deposit_service._config")
    @mock.patch("core.slh_deposit_service.Web3")
    @mock.patch("core.slh_deposit_service.assert_supply_unchanged")
    @mock.patch("core.slh_deposit_service.is_quarantined_bsc_address", return_value=False)
    def test_deposit_verification_stops_before_reading_transaction_on_supply_mismatch(
        self, quarantine, guard, web3_class, config
    ):
        config.return_value = {
            "rpc": "https://rpc.example.invalid",
            "treasury_wallet": TREASURY,
            "token_contract": TOKEN,
            "confirmations": 15,
        }
        guard.side_effect = ValueError("SLH_SUPPLY_MISMATCH")
        web3_instance = web3_class.return_value

        result = verify_slh_deposit("0x" + "ab" * 32)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "SLH_SUPPLY_MISMATCH")
        guard.assert_called_once_with(web3_instance, TOKEN)
        web3_instance.eth.get_transaction_receipt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
