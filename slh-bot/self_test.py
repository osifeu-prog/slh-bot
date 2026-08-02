import subprocess, json, os, time

def run(cmd):
    try: return subprocess.check_output(cmd, shell=True, text=True).strip()
    except: return "❌"

def test_all():
    results = []
    # Bot
    pid = run("pgrep -af bot_stable.py")
    results.append(("Bot", "✅" if pid else "❌"))
    # DB
    db_exists = os.path.exists("db.json")
    results.append(("DB", "✅" if db_exists else "❌"))
    # Students
    try:
        with open("db.json") as f: db = json.load(f)
        students = len(db.get("students", {}))
        results.append(("Students", f"{students}"))
    except:
        results.append(("Students", "❌"))
    # Agent – send test command and wait for outbox
    agent_ok = False
    try:
        with open("db.json") as f: db = json.load(f)
        # clear old outbox for clean test
        if "agents" in db and "mytermux" in db["agents"]:
            db["agents"]["mytermux"]["outbox"] = []
            db["agents"]["mytermux"]["inbox"].append({"command": "whoami", "time": time.time()})
            with open("db.json","w") as f: json.dump(db, f)
            time.sleep(3)  # wait for agent worker
            with open("db.json") as f: db = json.load(f)
            out = db.get("agents",{}).get("mytermux",{}).get("outbox",[])
            if out and "u0_a364" in out[-1]:
                agent_ok = True
    except: pass
    results.append(("Agent", "✅" if agent_ok else "❌"))
    # Ollama
    ollama = run("pgrep -f 'ollama serve'")
    results.append(("Ollama", "✅" if ollama else "❌"))
    # Disk
    disk = run("df -h . | tail -1 | awk '{print $5}'")
    results.append(("Disk", disk))
    # Recent errors (last 50 lines only)
    err_count = run("tail -n 50 logs/error.log 2>/dev/null | wc -l")
    results.append(("Errors", err_count))
    return results

if __name__ == "__main__":
    for name, status in test_all():
        print(f"{name}: {status}")
