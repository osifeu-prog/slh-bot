from datetime import datetime
from zoneinfo import ZoneInfo

import state_manager
from core import holiday_campaign


def test_holiday_campaign_is_only_active_on_2026_09_11():
    tz = ZoneInfo("Asia/Jerusalem")
    assert holiday_campaign.is_active(datetime(2026, 9, 11, 12, 0, tzinfo=tz))
    assert not holiday_campaign.is_active(datetime(2026, 9, 12, 12, 0, tzinfo=tz))
    assert not holiday_campaign.is_active(datetime(2026, 10, 2, 12, 0, tzinfo=tz))


def test_holiday_campaign_is_expired_and_never_eligible_now(monkeypatch):
    db = {
        "users": {
            "123": {
                "joined": True,
                "referral": {"count": 1},
                "campaigns": {
                    holiday_campaign.CAMPAIGN_ID: {
                        "entered_at": "2026-10-02T10:00:00+03:00"
                    }
                },
            }
        }
    }
    monkeypatch.setattr(state_manager, "load_db", lambda: db)

    now = datetime(2026, 10, 2, 12, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
    decision = holiday_campaign.eligibility("123", now=now)

    assert decision["eligible"] is False
    assert decision["reason"] == "CAMPAIGN_EXPIRED"
    assert decision["amount"] == 100_000
