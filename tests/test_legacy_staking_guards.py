import pytest

from core import economy_service


def test_stake_credits_is_disabled():
    with pytest.raises(RuntimeError, match="staking_service.stake_locked"):
        economy_service.stake_credits("1", 10)


def test_unstake_credits_is_disabled():
    with pytest.raises(RuntimeError, match="staking_service.unstake_locked"):
        economy_service.unstake_credits("1", 10)
