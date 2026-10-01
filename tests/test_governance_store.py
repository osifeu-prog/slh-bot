import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import governance_store


class GovernanceStoreTests(unittest.TestCase):
    def test_load_prefers_canonical_db_state(self):
        canonical = {
            "version": 1,
            "proposals": [{"id": 6}],
            "source_of_truth": "state/db.json",
        }
        legacy = {"version": 1, "proposals": [{"id": 1}]}

        with tempfile.TemporaryDirectory() as td:
            legacy_path = Path(td) / "governance.json"
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
            with patch.object(governance_store, "LEGACY_GOV_PATH", legacy_path), \
                 patch.object(governance_store, "load_db", return_value={"governance": canonical}):
                self.assertEqual(governance_store.load_governance(), canonical)

    def test_load_falls_back_to_legacy_without_writing(self):
        legacy = {
            "version": 1,
            "proposals": [{"id": 6}],
            "source_of_truth": "state/db.json",
        }

        with tempfile.TemporaryDirectory() as td:
            legacy_path = Path(td) / "governance.json"
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
            with patch.object(governance_store, "LEGACY_GOV_PATH", legacy_path), \
                 patch.object(governance_store, "load_db", return_value={}):
                self.assertEqual(governance_store.load_governance(), legacy)

    def test_ensure_canonical_migrates_legacy_and_preserves_all_fields(self):
        legacy = {
            "version": 1,
            "proposals": [{"id": 1}, {"id": 6}],
            "individual_votes": {"p1_owner": {"choice": "yes"}},
            "rules": {"pass_threshold": 0.6},
            "source_of_truth": "state/db.json",
        }
        db = {}

        def fake_atomic_update(mutator):
            return mutator(db)

        with tempfile.TemporaryDirectory() as td:
            legacy_path = Path(td) / "governance.json"
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
            with patch.object(governance_store, "LEGACY_GOV_PATH", legacy_path), \
                 patch.object(governance_store, "atomic_update", side_effect=fake_atomic_update):
                result = governance_store.ensure_canonical()

        self.assertEqual(result["proposals"], legacy["proposals"])
        self.assertEqual(result["individual_votes"], legacy["individual_votes"])
        self.assertEqual(result["rules"], legacy["rules"])
        self.assertEqual(db["governance"], result)
        self.assertEqual(result["source_of_truth"], "state/db.json")



    def test_record_vote_updates_governance_points_and_slh_snapshot(self):
        db = {
            "users": {
                "42": {
                    "role": "student",
                    "wallet": {"token_balance": 123.5, "live_token_balance": 120.0},
                    "gamification": {"points": 100},
                }
            },
            "governance": {
                "source_of_truth": "state/db.json",
                "rules": {"vote_weights": {"student": 1}, "pass_threshold": 0.6},
                "proposals": [{
                    "id": 9,
                    "status": "open",
                    "votes": {"yes": 0, "no": 0, "abstain": 0, "weighted_yes": 0, "weighted_no": 0},
                }],
                "individual_votes": {},
            },
        }

        def fake_atomic_update(mutator):
            return mutator(db)

        with patch.object(governance_store, "atomic_update", side_effect=fake_atomic_update):
            result = governance_store.record_vote(
                proposal_id=9,
                voter_uid="42",
                choice="yes",
                reward_points=10,
                now="2026-10-01T10:00:00+00:00",
            )

        self.assertEqual(result["status"], "recorded")
        self.assertEqual(result["weight"], 1)
        self.assertEqual(result["points_awarded"], 10)
        self.assertEqual(result["points_after"], 110)
        self.assertEqual(result["slh_context"]["token_balance"], 123.5)
        self.assertEqual(db["governance"]["proposals"][0]["votes"]["weighted_yes"], 1)
        self.assertEqual(db["users"]["42"]["gamification"]["points"], 110)
        self.assertEqual(len(db["users"]["42"]["points_ledger"]), 1)
        self.assertEqual(
            db["users"]["42"]["points_ledger"][0]["meta"]["idempotency_key"],
            "governance_vote:9:42",
        )

        with patch.object(governance_store, "atomic_update", side_effect=fake_atomic_update):
            again = governance_store.record_vote(
                proposal_id=9,
                voter_uid="42",
                choice="yes",
                reward_points=10,
            )

        self.assertEqual(again["status"], "already_voted")
        self.assertEqual(db["users"]["42"]["gamification"]["points"], 110)
        self.assertEqual(len(db["users"]["42"]["points_ledger"]), 1)

    def test_record_vote_rejects_closed_proposal(self):
        db = {
            "users": {"42": {"role": "student", "gamification": {"points": 100}}},
            "governance": {
                "rules": {"vote_weights": {"student": 1}},
                "proposals": [{"id": 9, "status": "approved", "votes": {}}],
            },
        }

        def fake_atomic_update(mutator):
            return mutator(db)

        with patch.object(governance_store, "atomic_update", side_effect=fake_atomic_update):
            with self.assertRaisesRegex(ValueError, "PROPOSAL_CLOSED"):
                governance_store.record_vote(
                    proposal_id=9,
                    voter_uid="42",
                    choice="yes",
                    reward_points=10,
                )

if __name__ == "__main__":
    unittest.main()
