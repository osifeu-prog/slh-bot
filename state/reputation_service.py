from state.reputation_engine import award_reputation


def reward_user(user_id, action):
    try:
        return award_reputation(user_id, action)
    except Exception as e:
        return {
            "error": str(e)
        }
