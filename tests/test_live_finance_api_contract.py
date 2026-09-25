from pathlib import Path
import unittest


class LiveFinanceApiContractTests(unittest.TestCase):
    def test_staking_mutation_is_not_disabled(self):
        source = Path("webapp.py").read_text(encoding="utf-8")
        self.assertNotIn("STAKING_MUTATION_DISABLED", source)
        self.assertIn('@app.route("/api/v1/staking", methods=["POST"])', source)
        self.assertIn('@app.route("/api/v1/staking/unstake", methods=["POST"])', source)
        self.assertIn("staking_service.stake_locked(", source)
        self.assertIn("staking_service.unstake_locked(", source)

    def test_bnb_claim_is_server_authenticated(self):
        source = Path("webapp.py").read_text(encoding="utf-8")
        self.assertIn('@app.route("/api/wallet/bnb/claim", methods=["POST"])', source)
        route = source.split('@app.route("/api/wallet/bnb/claim", methods=["POST"])', 1)[1]
        route = route.split('@app.route("/api/wallet/bnb")', 1)[0]
        self.assertIn("authenticated_uid()", route)
        self.assertIn("settle_bnb_deposit", route)

    def test_mini_app_has_live_controls(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("submitStake()", source)
        self.assertIn("claimBnbDeposit()", source)
        self.assertIn("/api/v1/staking", source)
        self.assertIn("/api/wallet/bnb/claim", source)


if __name__ == "__main__":
    unittest.main()
