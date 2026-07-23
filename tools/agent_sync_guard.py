import json
import shutil
import datetime
import os

DB="state/db.json"
AGENTS="state/agents.json"

os.makedirs("state/backups",exist_ok=True)

stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

shutil.copy2(
    AGENTS,
    f"state/backups/agents_mirror_{stamp}.json"
)

db=json.load(open(DB,encoding="utf8"))

agents=db.get("agents",{})

for name,a in agents.items():

    a.setdefault("name",name)
    a.setdefault("state","idle")
    a.setdefault("role","agent")
    a.setdefault("inbox",[])
    a.setdefault("history",[])
    a.setdefault("permissions",[])

with open(
    AGENTS,
    "w",
    encoding="utf8"
) as f:
    json.dump(
        agents,
        f,
        indent=2,
        ensure_ascii=False
    )

print("SYNC OK")
print("Agents:",len(agents))
