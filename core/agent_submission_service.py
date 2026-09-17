from datetime import datetime, timezone
from uuid import uuid4

import state_manager

APPROVAL_REWARD = 40


def _submission_id():
    return f"AS-{uuid4().hex}"


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
        normalized = agent_name.casefold()
        for submission in submissions:
            if (
                str(submission.get("uid")) == uid
                and str(submission.get("agent_name", "")).strip().casefold() == normalized
                and submission.get("status", "pending") == "pending"
            ):
                raise ValueError("SUBMISSION_ALREADY_PENDING")

        submission = {
            "id": _submission_id(),
            "uid": uid,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "meta": dict(meta),
        }
        submissions.append(submission)

        wallet = users[uid].setdefault("wallet", {})
        return {
            "submission": submission,
            "submission_id": submission["id"],
            "credits": wallet.get("credits", 0),
            "reward": 0,
            "status": "pending",
        }

    return state_manager.atomic_update(mutate)


def approve_agent_submission(submission_id, meta=None):
    """Approve one pending submission and grant exactly the policy reward once."""
    submission_id = str(submission_id).strip()
    meta = meta or {}
    if not submission_id:
        raise ValueError("SUBMISSION_NOT_FOUND")

    def mutate(db):
        submissions = db.setdefault("agent_submissions", [])
        index = next(
            (
                i for i, sub in enumerate(submissions)
                if str(sub.get("id", "")) == submission_id
            ),
            None,
        )
        if index is None:
            raise ValueError("SUBMISSION_NOT_FOUND")

        submission = submissions[index]
        if submission.get("status", "pending") != "pending":
            raise ValueError("SUBMISSION_NOT_PENDING")

        creator_uid = str(submission.get("uid", ""))
        agent_name = str(submission.get("agent_name", "")).strip()
        if not creator_uid or not agent_name:
            raise ValueError("INVALID_SUBMISSION")

        users = db.setdefault("users", {})
        if creator_uid not in users:
            raise ValueError("USER_NOT_FOUND")

        marketplace = db.setdefault("marketplace", [])
        for item in marketplace:
            if (
                str(item.get("creator")) == creator_uid
                and str(item.get("name", "")).strip().casefold() == agent_name.casefold()
            ):
                raise ValueError("AGENT_ALREADY_APPROVED")

        now = datetime.now(timezone.utc).isoformat()
        marketplace.append({
            "name": agent_name,
            "creator": creator_uid,
            "approved_at": now,
            "submission_id": submission_id,
        })

        wallet = users[creator_uid].setdefault("wallet", {})
        before = wallet.get("credits", 0)
        after = before + APPROVAL_REWARD
        wallet["credits"] = after

        submission["status"] = "approved"
        submission["approved_at"] = now
        submission["approved_by"] = str(meta.get("approved_by", ""))

        db.setdefault("ledger", []).append({
            "time": now,
            "uid": creator_uid,
            "before": before,
            "amount": APPROVAL_REWARD,
            "after": after,
            "reason": "agent:approval_reward",
            "meta": {
                **meta,
                "agent_name": agent_name,
                "submission_id": submission_id,
                "policy_reward": APPROVAL_REWARD,
            },
        })

        return {
            "creator_uid": creator_uid,
            "agent_name": agent_name,
            "credits": after,
            "reward": APPROVAL_REWARD,
            "submission_id": submission_id,
            "status": "approved",
        }

    return state_manager.atomic_update(mutate)
