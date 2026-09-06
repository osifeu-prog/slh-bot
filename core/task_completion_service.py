"""Atomic legacy task completion authority.

The Telegram /task_done command historically targets state/db.json -> tasks.
This service keeps that compatibility path while making completion + reward
one lock-protected mutation with an idempotency key.
"""

from datetime import datetime, timezone

import state_manager


def complete_task(uid, task_id, meta=None):
    uid = str(uid)
    task_id = str(task_id).strip()
    meta = dict(meta or {})

    if not task_id:
        raise ValueError("TASK_NOT_FOUND")

    def mutate(db):
        users = db.setdefault("users", {})
        if uid not in users:
            raise ValueError("USER_NOT_FOUND")

        tasks = db.setdefault("tasks", {})
        task = tasks.get(task_id)
        if task is None:
            raise ValueError("TASK_NOT_FOUND")

        done_by = task.setdefault("done_by", [])
        if any(str(x) == uid for x in done_by):
            raise ValueError("TASK_ALREADY_COMPLETED")

        # Only explicitly complete/active tasks are eligible.  This preserves
        # the old task model while preventing accidental reward issuance for
        # arbitrary DB keys.
        status = str(task.get("status", "active")).lower()
        if status not in {"active", "open", "in_progress"}:
            if status in {"done", "completed"}:
                raise ValueError("TASK_ALREADY_COMPLETED")
            raise ValueError("TASK_NOT_FOUND")

        reward = float(task.get("reward", 0) or 0)
        if reward < 0:
            raise ValueError("INVALID_TASK_REWARD")

        user = users[uid]
        wallet = user.setdefault("wallet", {})
        before = float(wallet.get("credits", 0) or 0)
        after = before + reward

        done_by.append(uid)
        task["status"] = "done"
        task["progress"] = 100
        task["completed_at"] = datetime.now(timezone.utc).isoformat()

        ledger = db.setdefault("ledger", [])
        key = f"task:{uid}:{task_id}"
        entry_meta = {**meta, "idempotency_key": key, "task_id": task_id}

        if reward:
            wallet["credits"] = after
            ledger.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "uid": uid,
                "before": before,
                "amount": reward,
                "after": after,
                "reason": "task:completion_reward",
                "meta": entry_meta,
            })

        return {
            "task_id": task_id,
            "reward": reward,
            "credits": after,
            "status": "completed",
        }

    return state_manager.atomic_update(mutate)
