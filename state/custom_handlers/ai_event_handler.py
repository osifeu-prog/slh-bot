import json, random, time
from core.event_bus import EventBus

def on_proposal_created(payload):
    print("📡 Event received:", payload)
    with open("state/db.json") as f:
        db = json.load(f)
    agents = db.get("agents", {})
    pid = str(payload.get("proposal_id"))
    votes = db.setdefault("votes", {})
    if pid not in votes:
        votes[pid] = {"yes": 0, "no": 0, "voters": {}}
    for aid, agent in agents.items():
        if agent.get("role") != "ai_assistant":
            continue
        choice = random.choice(["yes", "no"])
        votes[pid]["voters"][agent["name"]] = choice
        votes[pid][choice] = votes[pid].get(choice, 0) + 1
        agent.setdefault("inbox", []).append({
            "time": time.time(),
            "message": f"Auto-voted {choice} on proposal #{pid}"
        })
        print(f"🤖 {agent['name']} voted {choice}")
    with open("state/db.json", "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def register(bot=None):
    EventBus.subscribe("proposal_created", on_proposal_created)
    print("✅ AI Event Handler registered")
