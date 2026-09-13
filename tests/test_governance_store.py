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


if __name__ == "__main__":
    unittest.main()
