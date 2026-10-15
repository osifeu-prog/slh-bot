import unittest

from core.slh_trade_audit import audit_trades


def _db():
    return {
        "exchange_trades": [{
            "id": "T1", "buyer_uid": "buyer", "seller_uid": "seller",
            "slh_amount": "1.00000000", "price": "0.99000000",
            "credits_value": "0.99000000", "buy_order_id": "B1",
            "sell_order_id": "S1",
        }],
        "exchange_orders": {
            "B1": {"id": "B1", "uid": "buyer", "side": "buy", "limit_price": "1.00000000"},
            "S1": {"id": "S1", "uid": "seller", "side": "sell", "limit_price": "0.99000000"},
        },
        "exchange_order_archive": {},
        "slh_token_ledger": [{
            "event_id": "exchange:settlement_slh:T1",
            "kind": "exchange_settlement", "trade_id": "T1", "order_id": "S1",
            "seller_uid": "seller", "to_uid": "buyer",
            "from_uid": "__EXCHANGE_RESERVE__", "amount": 1.0,
        }],
        "ledger": [
            {"uid": "seller", "amount": 0.99, "reason": "exchange:settlement_credits",
             "meta": {"trade_id": "T1", "order_id": "S1"}},
            {"uid": "buyer", "amount": 0.01, "reason": "exchange:price_improvement_release",
             "meta": {"trade_id": "T1", "order_id": "B1"}},
        ],
    }


class SlhTradeAuditTests(unittest.TestCase):
    def test_complete_trade_settlement_passes(self):
        report = audit_trades(_db(), ["T1"])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["trades"][0]["status"], "PASS")

    def test_missing_slh_settlement_fails(self):
        db = _db()
        db["slh_token_ledger"] = []
        report = audit_trades(db, ["T1"])
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["trades"][0]["checks"]["slh_settlement_event_unique"])

    def test_wrong_order_party_fails(self):
        db = _db()
        db["exchange_orders"]["S1"]["uid"] = "someone-else"
        self.assertEqual(audit_trades(db, ["T1"])["status"], "FAIL")

    def test_missing_snapshot_sources_are_unknown(self):
        report = audit_trades({}, ["T1"])
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(report["trades"][0]["status"], "UNKNOWN")

    def test_duplicate_settlement_event_fails(self):
        db = _db()
        db["slh_token_ledger"].append(dict(db["slh_token_ledger"][0]))
        report = audit_trades(db, ["T1"])
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["trades"][0]["checks"]["slh_settlement_event_unique"])


if __name__ == "__main__":
    unittest.main()
