import unittest

from core.control_center import build_action, build_evidence, classify_action


class TestEvidenceContract(unittest.TestCase):
    def test_evidence_contract_is_structured_and_non_authoritative(self):
        record = build_evidence(
            sha="abc123",
            domain="bnb_opening",
            status="PENDING",
            source="bnb_opening_evidence",
            scope="read_only",
        )
        self.assertEqual(
            record,
            {
                "sha": "abc123",
                "domain": "bnb_opening",
                "status": "PENDING",
                "source": "bnb_opening_evidence",
                "scope": "read_only",
            },
        )

    def test_isolated_evidence_remains_explicitly_isolated(self):
        record = build_evidence(
            sha="abc123",
            domain="bnb_settlement",
            status="PASS",
            source="isolated_proof_harness",
            scope="isolated",
        )
        self.assertEqual(record["scope"], "isolated")
        self.assertEqual(record["status"], "PASS")

    def test_invalid_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            build_evidence(
                sha="abc123",
                domain="",
                status="PASS",
                source="test",
                scope="read_only",
            )
        with self.assertRaises(ValueError):
            build_evidence(
                sha="abc123",
                domain="test",
                status="PASS",
                source="test",
                scope="unknown",
            )

    def test_non_mutating_auto_action_can_be_described(self):
        record = build_action(
            action="collect_ci_evidence",
            reason="Current commit has completed CI runs but release evidence is not correlated.",
            safe=True,
        )
        self.assertEqual(record["mutation"], False)
        self.assertEqual(record["owner_required"], False)

    def test_mutating_action_requires_owner_approval(self):
        with self.assertRaises(ValueError):
            build_action(
                action="deploy",
                reason="Deploy release",
                safe=False,
                mutation=True,
                owner_required=False,
            )

    def test_safe_action_cannot_mutate(self):
        with self.assertRaises(ValueError):
            build_action(
                action="deploy",
                reason="Deploy release",
                safe=True,
                mutation=True,
                owner_required=True,
            )

    def test_known_read_only_action_is_auto_safe(self):
        record = classify_action(
            "collect_ci_evidence",
            "Collect existing CI evidence.",
        )
        self.assertEqual(record["safe"], True)
        self.assertEqual(record["mutation"], False)
        self.assertEqual(record["owner_required"], False)

    def test_known_sensitive_action_requires_owner(self):
        record = classify_action(
            "complete_bnb_opening_evidence",
            "Complete BNB opening evidence.",
        )
        self.assertEqual(record["safe"], False)
        self.assertEqual(record["mutation"], True)
        self.assertEqual(record["owner_required"], True)

    def test_unknown_action_fails_closed_to_owner_required(self):
        record = classify_action(
            "future_action_not_yet_reviewed",
            "This action has not been reviewed.",
        )
        self.assertEqual(record["safe"], False)
        self.assertEqual(record["mutation"], True)
        self.assertEqual(record["owner_required"], True)


if __name__ == "__main__":
    unittest.main()
