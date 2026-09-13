from datetime import datetime, timezone

import state_manager

APPROVAL_REWARD = 40


def submit_agent(uid, agent_name, meta=None):
    """Create a pending agent submission without issuing Credits."""
    uid = str(uid)
    agent_name = str(agent_name).strip()
    meta = meta or {}

    if not agent_name:
        raise ValueError("INVALID_AGENT_NAME")

    def mutate(db):
        users = db.setdefault("users", {})
        if uid not in users:
            raise ValueError("USER_NOT_FOUND")

        submissions = db.setdefault("agent_submissions", [])

        for submission in submissions:
            if (
                str(submission.get("uid")) == uid
                and str(submission.get("agent_name", "")).strip().casefold()
                == agent_name.casefold()
            ):
                raise ValueError("SUBMISSION_ALREADY_PENDING")

        submission = {
            "uid": uid,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "meta": dict(meta),
        }
        submissions.append(submission)

        return {
            "submission": submission,
            "credits": users[uid].setdefault("wallet", {}).get("credits", 0),
            "reward": 0,
            "status": "pending",
        }

    return state_manager.atomic_update(mutate)


def approve_agent_submission(submission_id, meta=None):
    """Approve one pending submission using the fixed policy reward."""
    meta = meta or {}
    submission_id = int(submission_id)

    from core import economy_service

    result = economy_service.approve_agent_submission(
        submission_id=submission_id,
        reward=APPROVAL_REWARD,
        meta={**meta, "policy_reward": APPROVAL_REWARD},
    )
    result["reward"] = APPROVAL_REWARD
    return result
