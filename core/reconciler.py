import state_manager

def reconcile():
    changes = []

    def mutate(db):
        # ניקוי test tasks
        tasks = db.get("tasks", {})
        clean_tasks = {
            k: v for k, v in tasks.items()
            if not any(
                x in k.lower() or x in v.get("title", "").lower()
                for x in ["test", "lifecycle"]
            )
        }

        removed = len(tasks) - len(clean_tasks)
        if removed:
            db["tasks"] = clean_tasks
            changes.append(f"הוסרו {removed} משימות test/lifecycle")

        # וידוא wallet לכל משתמש
        for uid, user in db.get("users", {}).items():
            if "wallet" not in user:
                user["wallet"] = {
                    "credits": 0,
                    "staked": 0,
                    "token_balance": 0
                }
                changes.append(f"נוסף wallet ל-{uid}")

    state_manager.atomic_update(mutate)

    return "✅ Reconciler:\n" + (
        "\n".join(f"• {c}" for c in changes)
        if changes else
        "• אין שינויים"
    )
