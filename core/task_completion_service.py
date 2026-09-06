"""Retry-safe task completion workflow.

Task state is stored in state/db.json and credits are issued only through the
Economy Authority. Completion and payment are therefore two lock-protected
operations, with the reward idempotency key making retries safe.
"""

from datetime import datetime, timezone

import state_manager
from core import economy_service


def complete_task(uid, task_id, meta=None):
    uid = str(uid)
    task_id = str(task_id).strip()
    meta = dict(meta or {})
    reward_key = f"task:{uid}:{task_id}:reward"

    if not task_id:
        raise ValueError("TASK_NOT_FOUND")

    def mark_complete(db):
        users = db.setdefault("users", {})
        if uid not in users:
            raise ValueError("USER_NOT_FOUND")

        tasks = db.setdefault("tasks", {})
        task = tasks.get(task_id)
        if task is None:
            raise ValueError("TASK_NOT_FOUND")

        done_by = task.setdefault("done_by", [])
        already_done = any(str(x) == uid for x in done_by)

        status = str(task.get("status", "active")).lower()
        if status not in {"active", "open", "in_progress", "done", "completed"}:
            raise ValueError("TASK_NOT_FOUND")
        if status in {"done", "completed"} and not already_done:
            raise ValueError("TASK_NOT_FOUND")

        reward = float(task.get("reward", 0) or 0)
        if reward < 0:
            raise ValueError("INVALID_TASK_REWARD")

        if not already_done:
            done_by.append(uid)
            task["status"] = "done"
            task["progress"] = 100
            task["completed_at"] = datetime.now(timezone.utc).isoformat()

        reward_recorded = any(
            entry.get("meta", {}).get("idempotency_key") == reward_key
            for entry in db.get("ledger", [])
        )

        return {
            "task_id": task_id,
            "reward": reward,
            "already_completed": already_done,
            "reward_recorded": reward_recorded,
        }

    result = state_manager.atomic_update(mark_complete)

    if result["reward"] <= 0 or result["reward_recorded"]:
        return {
            **result,
            "status": "completed",
            "reward_status": "already_paid" if result["reward_recorded"] else "paid",
        }

    try:
        credits = economy_service.record_transaction(
            uid,
            result["reward"],
            reason="task:completion_reward",
            meta={
                **meta,
                "idempotency_key": reward_key,
                "task_id": task_id,
            },
        )
    except Exception:
        return {
            **result,
            "status": "completed",
            "reward_status": "pending",
        }

    return {
        **result,
        "status": "completed",
        "reward_status": "paid",
        "credits": credits,
    }
