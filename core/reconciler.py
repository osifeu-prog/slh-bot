import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("state/db.json")

def reconcile():
    """בודק תקינות DB, מנקה test tasks, מוודא onboarding_completed וכו'. מחזיר סיכום."""
    if not DB_PATH.exists():
        return "❌ db.json לא קיים"

    try:
        db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return f"❌ שגיאה בקריאת db.json: {e}"

    changes = []

    # 1) ניקוי test/lifecycle tasks
    tasks = db.get("tasks", {})
    before = len(tasks)
    clean_tasks = {
        k: v for k, v in tasks.items()
        if not any(x in k.lower() or x in v.get("title", "").lower() for x in ["test", "lifecycle"])
    }
    removed = before - len(clean_tasks)
    if removed:
        db["tasks"] = clean_tasks
        changes.append(f"הוסרו {removed} משימות test/lifecycle")

    # 2) וידוא שלכל משתמש יש onboarding_completed (False ברירת מחדל)
    for uid, user in db.get("users", {}).items():
        if "onboarding_completed" not in user:
            user["onboarding_completed"] = False
            changes.append(f"נוסף onboarding_completed=False ל־{uid}")

    # 3) וידוא wallet קיים לכל משתמש
    for uid, user in db.get("users", {}).items():
        if "wallet" not in user:
            user["wallet"] = {"credits": 0, "staked": 0, "token_balance": 0}
            changes.append(f"נוסף wallet ריק ל־{uid}")

    # 4) עדכון progress_tracker לפי tasks קיימים (לא חובה)
    # ...

    if changes:
        DB_PATH.write_text(
            json.dumps(db, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    summary = "✅ Reconciler סיים:\n"
    summary += "\n".join(f"• {c}" for c in changes) if changes else "• אין שינויים נדרשים"
    return summary
