from copy import deepcopy

from tools.exchange_source_forensics import summarize_db


def test_forensics_matches_exchange_sources_without_mutating_state():
    db = {
        "exchange_order_archive": {
            "O0000000006": {
                "id": "O0000000006", "uid": "8789977826", "side": "sell",
                "status": "cancelled", "original_amount": 5, "remaining_amount": 0,
                "reserved_slh": 0, "archive_reason": "test_seed_retirement",
            },
        },
        "exchange_trade_archive": [
            {
                "id": "T8", "buy_order_id": "O0000000007",
                "sell_order_id": "O0000000006", "buyer_uid": "1234",
                "seller_uid": "8789977826", "slh_amount": 5,
                "price": 1, "credits_value": 5,
            },
        ],
        "ledger": [
            {
                "uid": "8789977826", "time": "2026-09-18T10:00:00Z",
                "reason": "exchange:sell_reserve", "before": 10,
                "amount": -5, "after": 5,
                "meta": {"order_id": "O0000000006"},
            },
            {
                "uid": "8789977826", "time": "2026-09-18T10:05:00Z",
                "reason": "exchange:cancel_release_slh", "before": 5,
                "amount": 0, "after": 5,
                "meta": {"order_id": "O0000000006"},
            },
            {
                "uid": "8789977826", "time": "2026-09-18T11:00:00Z",
                "reason": "exchange:manual_correction",
                "before": 5, "amount": 5, "after": 10,
                "meta": {
                    "order_id": "O0000000009",
                    "event_id": "correction:missed_release:O0000000009",
                },
            },
        ],
        "slh_token_ledger": [
            {
                "uid": "8789977826", "time": "2026-09-18T11:00:00Z",
                "kind": "exchange_correction", "amount": 5,
                "meta": {
                    "order_id": "O0000000009",
                    "event_id": "correction:missed_release:O0000000009",
                },
            },
        ],
    }
    before = deepcopy(db)

    report = summarize_db(db, "fixture")

    assert report["order_count"] == 1
    assert report["event_count"] == 4
    assert report["linked_trade_count"] == 1
    assert {row["order_id"] for row in report["events"]} == {
        "O0000000006", "O0000000009"
    }
    assert report["trades"][0]["trade_id"] == "T8"
    assert report["trades"][0]["buyer_uid_suffix"] == "1234"
    assert db == before
