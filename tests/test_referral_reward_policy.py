from core import referral_reward


def test_permanent_referral_reward_is_small_and_non_slh():
    assert referral_reward.SUCCESS_REFERRAL_CREDITS == 0.9
    assert referral_reward.SUCCESS_REFERRAL_POINTS == 10
    assert not hasattr(referral_reward, "SUCCESS_REFERRAL_SLH")


def test_holiday_campaign_is_not_part_of_permanent_referral_reward():
    source = open("core/referral_reward.py", encoding="utf-8").read()
    assert "holiday_campaign" not in source
    assert "100_000" not in source
