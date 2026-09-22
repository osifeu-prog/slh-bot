from unittest.mock import patch

from core import referral_rewards


def test_five_friend_milestone_is_idempotent():
    with patch("core.referral_rewards.grant") as grant:
        grant.return_value = {"credits": 500}
        first = referral_rewards.settle("123", 5)
        second = referral_rewards.settle("123", 5)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["threshold"] == 5
    assert first[0]["reward"]["credits"] == 500
    assert grant.call_count == 2
    assert grant.call_args_list[0].kwargs["idempotency_key"] == "referral-milestone:5:123"
    assert grant.call_args_list[1].kwargs["idempotency_key"] == "referral-milestone:5:123"


def test_milestone_not_reached():
    with patch("core.referral_rewards.grant") as grant:
        assert referral_rewards.settle("123", 4) == []
        grant.assert_not_called()
