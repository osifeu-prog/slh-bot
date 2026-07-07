path = "bot_stable.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    db.setdefault("students", {})[uid] = {
        "name": name,
        "group": group,
        "goal": goal,
        "registered": __import__("datetime").datetime.now().isoformat(),
        "referral_count": 0,
        "courses": {}
    }
    with open("state/db.json", "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)'''

new = '''    db.setdefault("students", {})[uid] = {
        "name": name,
        "group": group,
        "goal": goal,
        "registered": __import__("datetime").datetime.now().isoformat(),
        "referral_count": 0,
        "courses": {}
    }
    # Also create a "users" record so this person can use credits/balance/payments
    if uid not in db.setdefault("users", {}):
        db["users"][uid] = {
            "name": name,
            "created": __import__("datetime").datetime.now().isoformat(),
            "balance": 0
        }
    with open("state/db.json", "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)'''

count = content.count(old)
if count != 1:
    print(f"ERROR: expected 1 occurrence, found {count}, aborting")
else:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replacement done")
