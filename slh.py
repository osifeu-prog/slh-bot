import state_manager
import time, subprocess, json, os
J = type('J', (), {'log': lambda self, msg: print(f"[JOURNAL] {msg}")})()
E = type('E', (), {'run': lambda self, cmd: subprocess.getoutput(cmd)})()
DB_PATH = "state/db.json"
def load_db():
    with open(DB_PATH,'r') as f: return json.load(f)
def save_db(db):
    with open(DB_PATH,'w') as f: json.dump(db,f,indent=2)
def print_menu():
    print("\n"+"="*40+"\n SLH vNEXT - ADMIN PANEL ASCII\n"+"="*40)
    print("[1] Status [2] Users [3] Agents\n[4] Credits [5] Restart Bot [6] Exit\n"+"="*40)
def cmd_status(): J.log("System OK"); print(E.run("ps aux | grep python | grep -v grep"))
def cmd_users():
    db=load_db()
    for uid,u in db.get("users",{}).items(): print(f"{uid} | {u.get('name','?')} | {u.get('role')} | {u.get('credits',0)} Credits")
def cmd_agents():
    db=load_db()
    for aid,a in state_manager.get_agents().items(): print(f"{aid} | {a['name']} | {a['state']}")
def main():
    J.log("SLH vNEXT STARTED")
    while True:
        print_menu(); choice=input(">>> ").strip()
        if choice=="1": cmd_status()
        elif choice=="2": cmd_users()
        elif choice=="3": cmd_agents()
        elif choice=="5": os.system("pkill -f bot_stable.py && nohup python3 bot_stable.py > bot.log 2>&1 &")
        elif choice=="6": break
        else: print("פקודה לא ידועה")
        time.sleep(0.5)
if __name__=="__main__": main()
