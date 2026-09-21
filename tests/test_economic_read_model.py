import unittest
from unittest.mock import patch


class EconomicReadModelTests(unittest.TestCase):
    def test_normalizes_user_ledger_event(self):
        from core.economic_read_model import normalize_user_event

        event = normalize_user_event({
            "time": "2026-09-21T00:00:00+00:00",
            "uid": "user-1",
            "before": 10,
            "amount": -2.5,
            "after": 7.5,
            "reason": "purchase:item",
            "meta": {"item": "x"},
        })
        self.assertEqual(event["domain"], "user")
        self.assertEqual(event["account_id"], "user-1")
        self.assertEqual(event["amount"], -2.5)
        self.assertEqual(event["currency"], "credits")
        self.assertEqual(event["operation_ref"], "user:user-1:2026-09-21T00:00:00+00:00:purchase:item:-2.5")

    def test_normalizes_revenue_event(self):
        from core.economic_read_model import normalize_revenue_event

        event = normalize_revenue_event({
            "timestamp": "2026-09-21T00:00:00+00:00",
            "source": "telegram_stars",
            "amount": 5,
            "currency": "USD",
            "reference": "charge-1",
            "uid": "user-1",
            "meta": {},
        })
        self.assertEqual(event["domain"], "revenue")
        self.assertEqual(event["account_id"], "user-1")
        self.assertEqual(event["operation_ref"], "charge-1")
        self.assertEqual(event["currency"], "USD")

    def test_normalizes_agent_event(self):
        from core.economic_read_model import normalize_agent_event

        event = normalize_agent_event({
            "timestamp": "2026-09-21T00:00:00+00:00",
            "operation_id": "op-1",
            "entry_type": "transfer_credit",
            "account": "agent-2",
            "counterparty": "agent-1",
            "amount": 3,
            "before": 0,
            "after": 3,
            "actor": "owner",
            "reason": "work",
            "meta": {},
        })
        self.assertEqual(event["domain"], "agent")
        self.assertEqual(event["account_id"], "agent-2")
        self.assertEqual(event["operation_ref"], "op-1")
        self.assertEqual(event["currency"], "agent_credits")

    def test_read_model_does_not_mutate_sources(self):
        from core.economic_read_model import EconomicReadModel

        db = {
            "ledger": [{
                "time": "t",
                "uid": "u",
                "before": 1,
                "amount": 1,
                "after": 2,
                "reason": "r",
                "meta": {},
            }],
            "revenue_ledger": [{
                "timestamp": "t",
                "source": "s",
                "amount": 2,
                "currency": "USD",
                "reference": "ref",
                "uid": "u",
                "meta": {},
            }],
        }
        with patch("core.economic_read_model.state_manager.load_db", return_value=db),              patch("core.economic_read_model._agent_ledger", return_value=[]):
            model = EconomicReadModel()
            before = repr(db)
            result = model.events(limit=20)
            self.assertTrue(result)
            self.assertEqual(repr(db), before)

    def test_events_are_deterministically_sorted(self):
        from core.economic_read_model import EconomicReadModel

        db = {
            "ledger": [
                {"time": "2026-09-21T00:00:02+00:00", "uid": "u", "before": 1, "amount": 1, "after": 2, "reason": "b", "meta": {}},
                {"time": "2026-09-21T00:00:01+00:00", "uid": "u", "before": 0, "amount": 1, "after": 1, "reason": "a", "meta": {}},
            ],
            "revenue_ledger": [],
        }
        with patch("core.economic_read_model.state_manager.load_db", return_value=db),              patch("core.economic_read_model._agent_ledger", return_value=[]):
            events = EconomicReadModel().events(limit=20)
        self.assertEqual(events[0]["timestamp"], "2026-09-21T00:00:01+00:00")
        self.assertEqual(events[1]["timestamp"], "2026-09-21T00:00:02+00:00")


if __name__ == "__main__":
    unittest.main()