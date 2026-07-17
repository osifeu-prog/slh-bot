from state.reputation_engine import award_reputation
from state.reputation_verifier import verify_action


def reward_user(user_id, action, evidence=None):

    ok, msg = verify_action(action, evidence)

    if not ok:
        return {
            "error": msg
        }

    return award_reputation(user_id, action)
