import json
from pathlib import Path

DB_PATH = Path("state/db.json")

def reconcile():
    if not DB_PATH.exists():
        return "❌ db.json לא קיים"
    try:
        db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return f"❌ שגיאה בקריאת db.json: {e}"
    changes = []
    # ניקוי test tasks
    tasks = db.get("tasks", {})
    clean_tasks = {k:v for k,v in tasks.items() if not any(x in k.lower() or x in v.get("title","").lower() for x in ["test","lifecycle"])}
    removed = len(tasks)-len(clean_tasks)
    if removed:
        db["tasks"] = clean_tasks
        changes.append(f"הוסרו {removed} משימות test/lifecycle")
    # וידוא wallet לכל משתמש
    for uid, user in db.get("users", {}).items():
        if "wallet" not in user:
            user["wallet"] = {"credits":0,"staked":0,"token_balance":0}
            changes.append(f"נוסף wallet ל-{uid}")
    if changes:
        DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    return "✅ Reconciler:\n" + ("\n".join(f"• {c}" for c in changes) if changes else "• אין שינויים")
