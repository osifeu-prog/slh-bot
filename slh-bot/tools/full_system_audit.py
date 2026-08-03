#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import json
import subprocess
from datetime import datetime
ROOT = os.getcwd()
RESULTS = []

def test(name, fn):
    try:
        status, data = fn()
    except Exception as e:
        status, data = "ERROR", str(e)
    RESULTS.append({"test": name, "status": status, "data": data})
    print(f"[{status}] {name}: {data}")

print("=== SLH FULL SYSTEM AUDIT v1.1 ===")

# 1. IDENTITY - תיקון: נבדוק ישירות את המשתנים
def t1():
    from core.identity import OWNER_TELEGRAM_ID, OWNER_VIRTUAL_PHONE, OWNER_ID
    from admin_utils import is_admin
    class M: 
        class U: id=8789977826
        from_user=U()
    admin_check = is_admin(M())
    return "PASS" if admin_check else "FAIL", f"TG:{OWNER_TELEGRAM_ID} PHONE:{OWNER_VIRTUAL_PHONE} ADMIN:{admin_check}"
test("01_IDENTITY", t1)

# 2. DB STATE
def t2():
    d=json.load(open("state/db.json", encoding="utf-8"))
    agents=json.load(open("state/agents.json", encoding="utf-8"))
    return "PASS", f"Users:{len(d['users'])} Agents:{len(agents)}"
test("02_DB_STATE", t2)

# 3. ASK HANDLER
def t3():
    txt=open("handlers/loader.py", encoding="utf-8").read()
    return "PASS" if "register_ask_handler" in txt else "FAIL", "advanced_ask_handler registered"
test("03_ASK_HANDLER", t3)

# 4. COMMANDS
def t4():
    txt=open("handlers/loader.py", encoding="utf-8").read()
    cmds = ["start","admin","ask","status","join"]
    found = [c for c in cmds if f"commands=['{c}']" in txt or f'commands=["{c}"]' in txt]
    status = "PASS" if "admin" in found else "WARN"
    return status, f"Found: {found}"
test("04_COMMANDS", t4)

# 5. GIT
def t5():
    out=subprocess.run("git log -1 --oneline", shell=True, capture_output=True, text=True).stdout
    return "PASS", out.strip()
test("05_GIT", t5)

# 6. UTF8
def t6():
    json.load(open("state/agents.json", encoding="utf-8"))
    return "PASS", "agents.json UTF8 OK"
test("06_UTF8", t6)

# 7. RUNTIME
def t7():
    try:
        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        import bot_stable
        return "PASS", "bot_stable import OK"
    except Exception as e:
        return "FAIL", str(e)

test("07_RUNTIME", t7)

report={"timestamp":datetime.now().isoformat(),"results":RESULTS}
open("FULL_SYSTEM_AUDIT.json","w",encoding="utf-8").write(json.dumps(report,indent=2,ensure_ascii=False))
print("\nReport saved to FULL_SYSTEM_AUDIT.json")







