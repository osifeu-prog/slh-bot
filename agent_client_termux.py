import requests, time, subprocess, json
TOKEN = "שם_הטוקן_שלך" # ניקח מ-allowed_ids.json
SERVER = "https://web-production-22f28.up.railway.app"

print("🤖 Termux Agent Online")
while True:
    try:
        r = requests.get(f"{SERVER}/get_tasks?device=termux", timeout=5)
        if r.ok and r.json().get('cmd'):
            cmd = r.json()['cmd']
            out = subprocess.getoutput(cmd)
            requests.post(f"{SERVER}/result", json={'device':'termux','out':out})
        time.sleep(3)
    except: time.sleep(10)
