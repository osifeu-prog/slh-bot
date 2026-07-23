import json
import shutil
import datetime
import os

print("="*60)
print("SLH STATE CONSOLIDATION v1")
print(datetime.datetime.now())
print("="*60)


db_file="state/db.json"
agents_file="state/agents.json"

# backup
os.makedirs("state/backups",exist_ok=True)

stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

backup=f"state/backups/agents_before_consolidation_{stamp}.json"

shutil.copy2(
    agents_file,
    backup
)

print()
print("BACKUP:")
print(backup)


# load db

with open(db_file,encoding="utf8") as f:
    db=json.load(f)


db_agents=db.get("agents",{})


# write agents mirror

with open(
    agents_file,
    "w",
    encoding="utf8"
) as f:

    json.dump(
        db_agents,
        f,
        indent=2,
        ensure_ascii=False
    )


print()
print("SYNC COMPLETE")



# validate

with open(agents_file,encoding="utf8") as f:
    agents=json.load(f)


print()
print("VALIDATION")
print("db.json agents:",len(db_agents))
print("agents.json:",len(agents))


missing=[
    x for x in db_agents
    if x not in agents
]

extra=[
    x for x in agents
    if x not in db_agents
]


print()
print("Missing:",missing)
print("Extra:",extra)



report={
    "time":str(datetime.datetime.now()),
    "db_agents":len(db_agents),
    "agents_json":len(agents),
    "missing":missing,
    "extra":extra
}


with open(
    "state/consolidation_report.json",
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
print("="*60)
print("✅ CONSOLIDATION FINISHED")
print(json.dumps(report,indent=2,ensure_ascii=False))
print("="*60)

