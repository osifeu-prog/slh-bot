"""Retry-safe task completion workflow.

Task state is stored in state/db.json and credits are issued only through the
Economy Authority. Completion and payment are therefore two lock-protected
operations, with the reward idempotency key making retries safe.
"""

from datetime import datetime, timezone

import state_manager
from core import economy_service


def complete_task(uid, task_id, meta=None, *, requester_chat_id=None, human_approval_id=None):
    uid = str(uid)
    task_id = str(task_id).strip()
    meta = dict(meta or {})
    reward_key = f"task:{uid}:{task_id}:reward"

    if not task_id:
        raise ValueError("TASK_NOT_FOUND")

    from core import human_intervention as hi
    gate = hi.request_or_authorize(
        action="task_complete",
        resource_id=task_id,
        requester_uid=uid,
        requester_chat_id=requester_chat_id,
        approval_id=human_approval_id,
    )
    if gate.get("status") != "authorized":
        return {**gate, "task_id": task_id}

    approval_request_id = gate.get("request_id")

    def record_result(success, detail):
        summary = str(detail)[:500]
        if approval_request_id:
            hi.finish_request(approval_request_id, success=success, detail=summary)
        else:
            hi.record_action_event(
                "action_completed" if success else "action_failed",
                actor_id=uid, action="task_complete", resource_id=task_id, detail=summary,
            )

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

    try:
        result = state_manager.atomic_update(mark_complete)
    except Exception as exc:
        record_result(False, "task completion state write failed: " + type(exc).__name__)
        raise

    if result["reward"] <= 0 or result["reward_recorded"]:
        payload = {
            **result,
            "status": "completed",
            "reward_status": "already_paid" if result["reward_recorded"] else "paid",
        }
        record_result(True, "task completed; " + payload["reward_status"])
        return payload

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
    except Exception as exc:
        payload = {
            **result,
            "status": "completed",
            "reward_status": "pending",
        }
        record_result(True, "task completed; reward pending: " + type(exc).__name__)
        return payload

    payload = {
        **result,
        "status": "completed",
        "reward_status": "paid",
        "credits": credits,
    }
    record_result(True, "task completed; reward paid")
    return payload
