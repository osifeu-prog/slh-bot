import os
import json
import shutil
import datetime
import subprocess


print("="*60)
print("🛡️ SLH HARDENING PIPELINE")
print(datetime.datetime.now())
print("="*60)


# ---------------- SNAPSHOT ----------------

print("\n[1] SNAPSHOT")

os.makedirs("state/backups",exist_ok=True)

stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

for f in [
    "state/db.json",
    "state/agents.json",
    "state/tasks.json"
]:

    if os.path.exists(f):

        target=f"state/backups/{os.path.basename(f)}_{stamp}"

        shutil.copy2(f,target)

        print("BACKUP:",target)



# ---------------- TASKS ----------------

print("\n[2] TASK STATE")

tasks="state/tasks.json"

if not os.path.exists(tasks):

    with open(tasks,"w",encoding="utf8") as f:
        json.dump({},f,indent=2)

    print("created tasks.json")

else:

    print("tasks.json exists")



# ---------------- AGENTS ----------------

print("\n[3] AGENT SCHEMA")

agents_file="state/db.json"

with open(agents_file,encoding="utf8") as f:
    db=json.load(f)


agents=db.get("agents",{})

now=datetime.datetime.now().isoformat()

fixed=0


for name,a in agents.items():

    changed=False


    defaults={

        "name":name,
        "state":"idle",
        "role":"agent",
        "inbox":[],
        "history":[],
        "permissions":[],
        "created":now

    }


    for k,v in defaults.items():

        if k not in a:

            a[k]=v
            changed=True


    if changed:

        fixed+=1



with open(agents_file,"w",encoding="utf8") as f:
    json.dump(db,f,indent=2,ensure_ascii=False)


print("Agents fixed:",fixed)
print("Agents total:",len(agents))



# ---------------- AGENTS JSON SYNC ----------------

print("\n[4] AGENTS JSON SYNC")


try:

    with open("state/agents.json",encoding="utf8") as f:
        aj=json.load(f)


    print("agents.json:",len(aj))


except:

    print("agents.json invalid")



# ---------------- ASK TEST ----------------

print("\n[5] ASK ROUTER")

try:

    from core.ask_router import route

    print(route("כמה סוכנים יש"))

except Exception as e:

    print("ASK ERROR:",e)



# ---------------- GIT ----------------

print("\n[6] GIT")

try:

    out=subprocess.check_output(
        ["git","status","--short"],
        text=True
    )

    print(out)

except Exception as e:

    print(e)



# ---------------- FINAL REPORT ----------------


report={

"time":str(datetime.datetime.now()),

"agents":len(agents),

"schema_fixed":fixed,

"tasks_exists":os.path.exists(tasks)

}


with open(
"state/hardening_report.json",
"w",
encoding="utf8"
) as f:

    json.dump(report,f,indent=2)


print("\n")
print("="*60)
print("✅ HARDENING COMPLETE")
print(json.dumps(report,indent=2))
print("="*60)

