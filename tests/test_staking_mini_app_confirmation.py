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
    assert "מועד שחרור משוער:" in preview
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



def test_mini_app_disables_cancel_during_inflight_stake_and_keeps_retry_idempotent():
    source = (ROOT / "mini_app.html").read_text(encoding="utf-8")
    confirm_start = source.index("async function confirmStake(){")
    cancel_start = source.index("function cancelStake(){", confirm_start)
    confirm = source[confirm_start:cancel_start]
    cancel_end = source.index("async function unstakePosition(positionId){", cancel_start)
    cancel = source[cancel_start:cancel_end]

    assert "__stakeConfirmationInFlight=true" in confirm
    assert "cancelButton.disabled=true" in confirm
    assert "client_request_id:pending.requestId" in confirm
    assert "__stakeConfirmationInFlight)return" in cancel
    assert "בדוק/י /positions לפני ניסיון נוסף" in cancel
