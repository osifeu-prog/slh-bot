import unittest
from unittest.mock import patch

from core import governance_store
import webapp


def governance_db():
    return {
        "users": {
            "42": {
                "role": "student",
                "wallet": {"token_balance": 12.0, "live_token_balance": 10.0},
                "gamification": {"points": 100},
            }
        },
        "governance": {
            "source_of_truth": "state/db.json",
            "rules": {"vote_weights": {"student": 1}, "pass_threshold": 0.6},
            "proposals": [{
                "id": 7,
                "title": "Canonical proposal",
                "description": "A proposal shared by Telegram and Mini App.",
                "status": "open",
                "created_by": "owner",
                "created_at": "2026-10-09T00:00:00+00:00",
                "votes": {
                    "yes": 0, "no": 0, "abstain": 0,
                    "weighted_yes": 0, "weighted_no": 0,
                },
            }],
            "individual_votes": {},
        },
    }


class GovernanceCanonicalFlowTests(unittest.TestCase):
    def test_create_proposal_writes_to_canonical_database_atomically(self):
        db = governance_db()

        def fake_atomic_update(mutator):
            return mutator(db)

        with patch.object(governance_store, "atomic_update", side_effect=fake_atomic_update):
            proposal = governance_store.create_proposal(
                title="New proposal",
                description="Visible to Mini App and Telegram.",
                created_by="42",
                now="2026-10-09T01:00:00+00:00",
            )

        self.assertEqual(proposal["id"], 8)
        self.assertEqual(db["governance"]["proposals"][-1]["title"], "New proposal")
        self.assertEqual(db["governance"]["proposals"][-1]["created_by"], "42")
        self.assertEqual(db["governance"]["source_of_truth"], "state/db.json")

    def test_finalize_proposal_updates_canonical_status_by_weighted_threshold(self):
        db = governance_db()
        proposal = db["governance"]["proposals"][0]
        proposal["votes"].update({"yes": 3, "no": 1, "weighted_yes": 3, "weighted_no": 1})

        def fake_atomic_update(mutator):
            return mutator(db)

        with patch.object(governance_store, "atomic_update", side_effect=fake_atomic_update):
            result = governance_store.finalize_proposal(proposal_id=7)

        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["weighted_yes"], 3)
        self.assertEqual(result["weighted_no"], 1)
        self.assertEqual(db["governance"]["proposals"][0]["status"], "approved")

    def test_minapp_vote_endpoint_requires_telegram_auth(self):
        with patch.object(webapp, "authenticated_uid", return_value=None):
            response = webapp.app.test_client().post(
                "/api/v1/governance/vote",
                json={"proposal_id": 7, "choice": "yes"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "TELEGRAM_AUTH_REQUIRED")

    def test_minapp_vote_endpoint_returns_canonical_receipt_and_is_idempotent(self):
        db = governance_db()

        def fake_atomic_update(mutator):
            return mutator(db)

        client = webapp.app.test_client()
        with patch.object(webapp, "authenticated_uid", return_value="42"), \
             patch.object(governance_store, "atomic_update", side_effect=fake_atomic_update), \
             patch("core.tokenomics.rewards_snapshot", return_value={"vote_points": 5}):
            first = client.post(
                "/api/v1/governance/vote",
                json={"proposal_id": 7, "choice": "yes"},
            )
            second = client.post(
                "/api/v1/governance/vote",
                json={"proposal_id": 7, "choice": "no"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["status"], "recorded")
        self.assertEqual(first.get_json()["proposal_id"], 7)
        self.assertEqual(first.get_json()["choice"], "yes")
        self.assertEqual(first.get_json()["weight"], 1)
        self.assertEqual(first.get_json()["points_awarded"], 5)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["status"], "already_voted")
        self.assertEqual(second.get_json()["choice"], "yes")
        self.assertEqual(db["governance"]["proposals"][0]["votes"]["weighted_yes"], 1)
        self.assertEqual(db["governance"]["proposals"][0]["votes"]["weighted_no"], 0)
        self.assertEqual(db["users"]["42"]["gamification"]["points"], 105)
        self.assertEqual(len(db["users"]["42"]["points_ledger"]), 1)


if __name__ == "__main__":
    unittest.main()
