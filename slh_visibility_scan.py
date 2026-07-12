import os,json,sqlite3,glob

print("="*50)
print("🚀 SLH PUBLICATION READINESS SCAN")
print("="*50)

print("\n📂 PROJECT FILES")
for f in [
"bot_stable.py",
"config.json",
"railway.json",
"allowed_ids.json",
"subscriptions.json",
"plugins.json",
"marketplace.json"
]:
    print("✅",f) if os.path.exists(f) else print("❌",f)


print("\n👥 USERS / ACCESS")

for f in [
"allowed_ids.json",
"subscriptions.json",
"state/users.json"
]:
    if os.path.exists(f):
        try:
            d=json.load(open(f))
            print("\n",f)
            print("records:",len(d))
            print(str(d)[:300])
        except:
            pass


print("\n💾 DATABASES")

for db in glob.glob("*.db"):
    try:
        con=sqlite3.connect(db)
        cur=con.cursor()
        tables=cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        print("\n",db)
        for t in tables:
            name=t[0]
            if name.startswith("sqlite"):
                continue
            count=cur.execute(
            f"SELECT COUNT(*) FROM {name}"
            ).fetchone()[0]
            print(" ",name,count)

        con.close()
    except:
        pass


print("\n🤖 COMMANDS")

cmds=[]

for f in glob.glob("*.py")+glob.glob("handlers/*.py")+glob.glob("plugins/*.py"):
    try:
        txt=open(f,errors="ignore").read()
        for line in txt.splitlines():
            if "commands=[" in line:
                cmds.append(line.strip())
    except:
        pass

print("commands:",len(cmds))
for c in cmds[:30]:
    print(c)


print("\n📡 TELEGRAM IDS FOUND")

import subprocess

r=subprocess.getoutput(
"grep -RhoE '[0-9]{7,}' . --include='*.py' --include='*.json' | sort -u"
)

print(r[:1000])


print("\n✅ SCAN COMPLETE")
