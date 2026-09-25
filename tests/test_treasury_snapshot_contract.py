import json
from pathlib import Path
import unittest

class TreasurySnapshotContractTests(unittest.TestCase):
    def test_gateway_logs_bsc_treasury_snapshot(self):
        source = Path("bot_gateway.py").read_text(encoding="utf-8")
        self.assertIn("from core.deposit_monitor import get_onchain_status", source)
        self.assertIn("[BSC] Treasury snapshot:", source)
        self.assertIn("BNB={chain.get('treasury_bnb')}", source)
        self.assertIn("SLH={chain.get('treasury_slh')}", source)

if __name__ == "__main__":
    unittest.main()
