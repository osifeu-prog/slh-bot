import json
import shutil
import datetime
import os


print("="*60)
print("SLH STATE SYNC HARDENING v2")
print(datetime.datetime.now())
print("="*60)


DB="state/db.json"
AGENTS="state/agents.json"


# backup
os.makedirs("state/backups",exist_ok=True)

stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

shutil.copy2(
    AGENTS,
    f"state/backups/agents_before_sync_{stamp}.json"
)

print("Backup created")


# load db

with open(DB,encoding="utf8") as f:
    db=json.load(f)


agents=db.get("agents",{})


# normalize

for name,a in agents.items():

    a.setdefault("name",name)
    a.setdefault("state","idle")
    a.setdefault("role","agent")
    a.setdefault("inbox",[])
    a.setdefault("history",[])
    a.setdefault("permissions",[])
    a.setdefault(
        "created",
        datetime.datetime.now().isoformat()
    )


# write mirror

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


print()
print("SYNC DONE")


# validate

with open(AGENTS,encoding="utf8") as f:
    mirror=json.load(f)


print()
print("DB:",len(agents))
print("agents.json:",len(mirror))


missing=[
x for x in agents
if x not in mirror
]

extra=[
x for x in mirror
if x not in agents
]


print("Missing:",missing)
print("Extra:",extra)


report={
"timestamp":str(datetime.datetime.now()),
"db":len(agents),
"mirror":len(mirror),
"missing":missing,
"extra":extra
}


with open(
"state/state_sync_report.json",
"w",
encoding="utf8"
) as f:

    json.dump(
        report,
        f,
        indent=2,
        ensure_ascii=False
    )


print()
print(json.dumps(report,indent=2))

print("="*60)
print("READY")
print("="*60)

