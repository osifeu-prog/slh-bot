from state.reputation_engine import award_reputation
from state.reputation_verifier import verify_action
from state.reputation_guard import (
    create_event_id,
    already_rewarded,
    register_event
)


def reward_user(user_id, action, evidence=None):

    ok, msg = verify_action(action, evidence)

    if not ok:
        return {
            "error": msg
        }

    event_id = create_event_id(
        user_id,
        action,
        evidence
    )

    if already_rewarded(event_id):
        return {
            "error": "Already rewarded"
        }

    result = award_reputation(
        user_id,
        action
    )

    register_event(event_id)

    return result
