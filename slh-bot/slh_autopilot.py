#!/usr/bin/env python3
import os, sys, json, subprocess, time
from datetime import datetime

FIX_MODE = "--fix" in sys.argv
LOG = []

def log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    line = f"[{now}] {msg}"
    print(line)
    LOG.append(line)

def run(cmd, shell=True):
    try:
        res = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=15)
        return res.returncode, (res.stdout + res.stderr).strip()
    except Exception as e:
        return 1, str(e)

def check_bot_running():
    rc, out = run("pgrep -f bot_stable.py")
    if rc == 0:
        pid = out.strip().split('\n')[0]
        log(f"✅ bot_stable.py רץ (PID {pid})")
        return True
    else:
        log("❌ bot_stable.py לא רץ")
        if FIX_MODE:
            log("🔧 מנסה להפעיל...")
            run("nohup python3 bot_stable.py > bot.log 2>&1 &")
            time.sleep(3)
            rc2, _ = run("pgrep -f bot_stable.py")
            if rc2 == 0:
                log("✅ הבוט עלה מחדש")
                return True
        return False

def check_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            json.load(f)
        log(f"✅ {filepath} תקין")
        return True
    except Exception as e:
        log(f"❌ {filepath} פגום: {e}")
        return False

def check_syntax():
    rc, out = run("python3 -m py_compile bot_stable.py handlers/advanced_ask_handler.py handlers/llm_handler.py handlers/loader.py 2>&1")
    if rc == 0:
        log("✅ Syntax OK על קבצי ליבה")
        return True
    else:
        log(f"❌ Syntax error:\n{out}")
        return False

def check_llm_import():
    code = "from handlers.llm_handler import query_llm_with_context; print('OK')"
    rc, out = run(f"python3 -c \"{code}\"")
    if rc == 0 and "OK" in out:
        log("✅ ייבוא query_llm_with_context הצליח")
        return True
    else:
        log(f"❌ כשל בייבוא LLM: {out}")
        return False

def fix_system_collector():
    path = "core/system_collector.py"
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        content = f.read()
    if "def init" in content:
        return
    if "def init(self)" in content and "def init" not in content:
        log("🔧 מתקן SystemCollector: init -> init")
        content = content.replace("def init(self):", "def init(self):")
        if "collector = SystemCollector()" not in content:
            content += "\ncollector = SystemCollector()\n"
        with open(path, 'w') as f:
            f.write(content)
        log("✅ SystemCollector תוקן")

def git_commit():
    rc, out = run("git status --short")
    if not out.strip():
        log("📦 אין שינויים ל־commit")
        return True
    run("git add -A")
    run(f'git commit -m "AutoPilot fix {datetime.now().strftime("%Y%m%d_%H%M%S")}"')
    rc, out = run("git push")
    if rc == 0:
        log("✅ Git push הצליח")
        return True
    else:
        log(f"❌ Git push נכשל: {out}")
        return False

def auto_fix():
    fix_system_collector()

log("🚀 SLH Autopilot מתחיל")
check_bot_running()
check_json("state/db.json")
check_json("state/agents.json")
check_syntax()
check_llm_import()

if FIX_MODE:
    auto_fix()
    git_commit()

with open("logs/autopilot.log", "a", encoding="utf-8") as f:
    f.write("\n".join(LOG) + "\n")
print("\n📋 לוג נשמר ב־logs/autopilot.log")
