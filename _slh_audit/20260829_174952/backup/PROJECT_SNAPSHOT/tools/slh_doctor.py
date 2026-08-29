import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP=os.path.join(ROOT,"slh-bot")

sys.path.insert(0,APP)

import json
import importlib


print("""
========================
 SLH OS DOCTOR v2
========================
""")

checks=[]

def check(name,fn):
    try:
        fn()
        print("[OK]   "+name)
        checks.append(True)
    except Exception as e:
        print("[FAIL] "+name)
        print("       ",e)
        checks.append(False)


check(
"profile_manager",
lambda: importlib.import_module("core.profile_manager")
)

check(
"academy_manager",
lambda: importlib.import_module("core.academy_manager")
)

check(
"academy_handler",
lambda: importlib.import_module("handlers.academy_handler")
)

check(
"lesson_handler",
lambda: importlib.import_module("handlers.lesson_handler")
)


def db_check():
    path="state/db.json"

    if not os.path.exists(path):
        raise Exception("missing state/db.json")

    with open(path,encoding="utf-8") as f:
        json.load(f)


check(
"state database",
db_check
)


print()

if all(checks):
    print("SLH STATUS: HEALTHY")
else:
    print("SLH STATUS: NEEDS ATTENTION")
