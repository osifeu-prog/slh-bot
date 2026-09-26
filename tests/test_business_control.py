from datetime import datetime, timezone
from handlers.business_control_handler import _iso

def test_iso_accepts_zulu_timestamp():
    assert _iso("2026-09-26T12:00:00Z") == datetime(2026,9,26,12,0,tzinfo=timezone.utc)

def test_iso_rejects_invalid_timestamp():
    assert _iso("not-a-date") is None
