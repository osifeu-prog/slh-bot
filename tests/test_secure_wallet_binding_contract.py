import importlib
import unittest
from pathlib import Path


class SecureWalletBindingContractTests(unittest.TestCase):
    def test_bnb_binding_authority_exists(self):
        from core import wallet_binding
        self.assertTrue(callable(wallet_binding.issue_challenge))
        self.assertTrue(callable(wallet_binding.verify_signature))
        self.assertTrue(callable(wallet_binding.get_binding))

    def test_bnb_settlement_authority_exists(self):
        from core import bnb_deposit_service
        self.assertTrue(callable(bnb_deposit_service.settle_bnb_deposit))

    def test_ton_binding_authority_is_callable(self):
        module = importlib.import_module("core.ton_wallet_binding")
        self.assertTrue(callable(module.issue_ton_challenge))
        self.assertTrue(callable(module.verify_ton_proof))
        self.assertTrue(callable(module.get_ton_binding))

    def test_ton_settlement_authority_is_callable(self):
        module = importlib.import_module("core.ton_deposit_service")
        self.assertTrue(callable(module.settle_ton_deposit))

    def test_unique_existing_handlers(self):
        loader = Path("handlers/loader.py").read_text(encoding="utf-8")
        self.assertEqual(loader.count('("p2p", "handlers.p2p_handler")'), 1)
        self.assertEqual(loader.count('("exchange", "handlers.exchange_handler")'), 1)
        self.assertEqual(loader.count('("wallet", "handlers.wallet_handler")'), 1)


if __name__ == "__main__":
    unittest.main()
