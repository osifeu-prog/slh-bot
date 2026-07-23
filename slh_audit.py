import os
import json
import sys
import subprocess
from collections import Counter
from datetime import datetime

print("=" * 60)
print("🧠 SLH OS FULL AUDIT")
print(datetime.now())
print("=" * 60)

def section(title):
    print("\n" + "-" * 50)
    print(title)
    print("-" * 50)

def ok(name, value):
    print(f"✅ {name}: {value}")

def warn(name, value):
    print(f"⚠️ {name}: {value}")

def fail(name, value):
    print(f"❌ {name}: {value}")


# Python
section("PYTHON")

ok("Python", sys.version.split()[0])


# psutil
section("SYSTEM RESOURCES")

try:
    import psutil

    ok(
        "RAM",
        f"{psutil.virtual_memory().percent}% used"
    )

    ok(
        "Disk",
        f"{psutil.disk_usage('.').percent}% used"
    )

except Exception as e:
    fail("psutil", e)



# DB
section("DATABASE")

DB="state/db.json"

try:
    with open(DB, encoding="utf-8") as f:
        db=json.load(f)

    ok("db.json", "loaded")

    for key in [
        "users",
        "agents",
        "tasks",
        "memory",
        "votes"
    ]:
        if key in db:
            ok(key, len(db[key]) if isinstance(db[key],dict) else db[key])
        else:
            warn(key,"missing")

except Exception as e:
    fail("DB",e)



# Agents
section("AGENTS")

try:
    agents=db.get("agents",{})

    ok("Agents count",len(agents))

    for aid,a in list(agents.items())[:3]:

        print("\nAgent:",aid)

        for field in [
            "name",
            "state",
            "role",
            "inbox",
            "history",
            "permissions",
            "created"
        ]:
            if field in a:
                print("  ✅",field)
            else:
                print("  ⚠️",field,"missing")

except Exception as e:
    fail("Agents",e)



# Backups
section("BACKUPS")

for f in os.listdir("state"):

    if "backup" in f.lower():

        print("📦",f)



# Bot handlers
section("BOT HANDLERS")

try:

    import bot_stable

    handlers=bot_stable.bot.message_handlers

    ok(
        "Total handlers",
        len(handlers)
    )


    commands=[]

    for h in handlers:

        commands.extend(
            h.get("filters",{})
            .get("commands",[])
        )


    count=Counter(commands)

    duplicates=[
        x for x in count.items()
        if x[1]>1
    ]

    if duplicates:
        warn(
            "Duplicate commands",
            duplicates
        )
    else:
        ok(
            "Duplicate commands",
            "none"
        )


    ask=[
        c for c in commands
        if c=="ask"
    ]

    ok(
        "ASK handlers",
        len(ask)
    )


except Exception as e:
    fail("Handlers",e)



# ASK Router
section("ASK ROUTER")

try:

    from core.ask_router import route

    result=route("כמה סוכנים יש")

    ok(
        "ASK test",
        result
    )

except Exception as e:
    fail("ASK",e)



# Files
section("STATE FILES")

for f in [
    "state/db.json",
    "state/agents.json",
    "state/tasks.json"
]:

    if os.path.exists(f):
        size=os.path.getsize(f)

        ok(
            f,
            f"{size} bytes"
        )

    else:
        warn(
            f,
            "missing"
        )


# Git
section("GIT")

try:

    out=subprocess.getoutput(
        "git status --short"
    )

    if out.strip():

        warn(
            "Git changes",
            "\n"+out
        )

    else:
        ok(
            "Git",
            "clean"
        )

except Exception as e:
    warn("Git",e)



# Docker
section("DOCKER")

try:

    out=subprocess.getoutput(
        "docker ps"
    )

    print(out)

except Exception as e:
    warn("Docker",e)



print("\n")
print("=" * 60)
print("✅ AUDIT FINISHED")
print("=" * 60)