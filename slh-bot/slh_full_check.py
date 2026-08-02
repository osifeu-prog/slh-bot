import os
import json
import subprocess
import datetime
import sys
from collections import defaultdict

REPORT = {
    "time": str(datetime.datetime.now()),
    "checks": {}
}

def section(name):
    print("\n" + "="*60)
    print(name)
    print("="*60)

def save():
    with open("slh_audit_report.json","w",encoding="utf-8") as f:
        json.dump(REPORT,f,indent=2,ensure_ascii=False)


# PYTHON
section("PYTHON")

REPORT["checks"]["python"] = sys.version
print(sys.version)


# RESOURCES
section("RESOURCES")

try:
    import psutil

    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent

    REPORT["checks"]["ram"]=ram
    REPORT["checks"]["disk"]=disk

    print("RAM:",ram,"%")
    print("DISK:",disk,"%")

except Exception as e:
    print("resource error",e)


# STATE
section("STATE")

for f in [
    "state/db.json",
    "state/agents.json",
    "state/tasks.json"
]:

    if os.path.exists(f):

        size=os.path.getsize(f)

        print("OK",f,size,"bytes")

        REPORT["checks"][f]={
            "exists":True,
            "size":size
        }

    else:

        print("MISSING",f)

        REPORT["checks"][f]={
            "exists":False
        }



# DATABASE
section("DATABASE")

try:

    with open("state/db.json",encoding="utf8") as f:
        db=json.load(f)

    for k in [
        "users",
        "agents",
        "tasks",
        "memory",
        "votes"
    ]:
        print(k,":",len(db.get(k,{})))

    REPORT["checks"]["db_counts"]={
        k:len(db.get(k,{}))
        for k in db
    }

except Exception as e:

    print("DB ERROR",e)



# AGENTS
section("AGENTS")

try:

    agents=db.get("agents",{})

    missing={}

    for name,a in agents.items():

        miss=[]

        for key in [
            "name",
            "state",
            "role",
            "inbox",
            "history",
            "permissions",
            "created"
        ]:

            if key not in a:
                miss.append(key)

        if miss:
            missing[name]=miss


    print("Agents:",len(agents))

    if missing:

        print("Schema problems:")

        for a,m in missing.items():
            print(a,m)

    else:
        print("All agents OK")


    REPORT["checks"]["agent_schema"]=missing


except Exception as e:

    print(e)



# HANDLERS
section("HANDLERS")

try:

    import bot_stable

    handlers=bot_stable.bot.message_handlers

    print("TOTAL:",len(handlers))


    cmds=defaultdict(list)

    for h in handlers:

        for c in h["filters"].get("commands",[]):

            cmds[c].append(
                str(h["function"])
            )


    duplicates={}

    for c,v in cmds.items():

        if len(v)>1:
            duplicates[c]=len(v)


    print("Duplicates:")

    for k,v in duplicates.items():
        print(k,v)


    REPORT["checks"]["handler_count"]=len(handlers)
    REPORT["checks"]["duplicates"]=duplicates


except Exception as e:

    print("handler error",e)



# ASK
section("ASK ROUTER")

try:

    from core.ask_router import route

    answer=route("כמה סוכנים יש")

    print(answer)

    REPORT["checks"]["ask"]=answer

except Exception as e:

    print(e)



# GIT
section("GIT")

try:

    out=subprocess.check_output(
        ["git","status","--short"],
        text=True
    )

    print(out)

    REPORT["checks"]["git"]=out

except Exception as e:

    print(e)



# DOCKER

section("DOCKER")

try:

    out=subprocess.check_output(
        ["docker","ps"],
        text=True
    )

    print(out)

except Exception as e:

    print("Docker unavailable")



save()


print("\nDONE")
print("Report saved: slh_audit_report.json")