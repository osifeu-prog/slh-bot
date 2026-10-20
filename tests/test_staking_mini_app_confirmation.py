from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mini_app_staking_requires_preview_before_posting():
    source = (ROOT / "mini_app.html").read_text(encoding="utf-8")
    preview_start = source.index("async function submitStake(){")
    confirm_start = source.index("async function confirmStake(){", preview_start)
    preview = source[preview_start:confirm_start]
    confirm_end = source.index("function cancelStake(){", confirm_start)
    confirm = source[confirm_start:confirm_end]

    assert "stakeConfirmPanel" in preview
    assert "mועד שחרור משוער" not in preview  # runtime label is composed from a localized date below
    assert "unlockAt.toLocaleString('he-IL')" in preview
    assert "fetch('/api/v1/staking'" not in preview
    assert "fetch('/api/v1/staking'" in confirm
    assert "client_request_id:pending.requestId" in confirm


def test_mini_app_staking_discloses_variable_revenue_share_without_promising_yield():
    source = (ROOT / "mini_app.html").read_text(encoding="utf-8")
    assert "80% מההכנסה הנקייה בפועל" in source
    assert "אין תשואה קבועה או מובטחת" in source
    assert "לא ניתן להציג אחוז תשואה צפוי אמין מראש" in source
    assert 'onclick="confirmStake()"' in source
    assert 'onclick="cancelStake()"' in source
