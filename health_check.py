import os, json, subprocess

def ok(n, r): print(("✅" if r else "❌"), n); return r

print("\n=== SLH UNIFIED HEALTH CHECK ===\n")

results = []

results.append(ok("bot.py exists", os.path.exists("bot.py")))
results.append(ok("kernel exists", os.path.exists("../slh_os_v4_real")))
results.append(ok("config exists", os.path.exists("config.json")))

try:
    cfg = json.load(open("config.json"))
    results.append(ok("token field exists", "BOT_TOKEN" in cfg))
except:
    results.append(False)

results.append(ok("python runtime", subprocess.call(["python3","--version"]) == 0))

print("\nTOTAL:", sum(results), "/", len(results))

if all(results):
    print("\nSYSTEM READY FOR DEPLOYMENT 🚀")
else:
    print("\nSYSTEM NEEDS FIX ⚠️")
