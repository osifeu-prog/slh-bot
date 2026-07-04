import re, subprocess, sys, json, os

os.chdir("/root/slh_clean")  # adjust if needed; use /data/data/com.termux/files/home/slh_clean for Termux
# Actually we'll use current working directory; assume we are in slh_clean
# But the script is run from anywhere? Better to cd to the right dir inside the script.
# We'll let the user call this script from slh_clean directory.

print("=== 1. Process check ===")
try:
    out = subprocess.check_output(["pgrep", "-a", "bot.py"], text=True).strip()
    print("Running:", out)
except subprocess.CalledProcessError:
    print("No bot.py process running")

print("\n=== 2. Syntax check ===")
try:
    import py_compile
    py_compile.compile("bot.py", doraise=True)
    print("Syntax OK")
except py_compile.PyCompileError as e:
    print(f"Syntax ERROR: {e}")
    # We will fix later

print("\n=== 3. Polling line & handlers ===")
with open("bot.py") as f:
    code = f.read()

poll_pos = code.find("bot.infinity_polling") if "bot.infinity_polling" in code else code.find("bot.polling")
if poll_pos != -1:
    print("Polling line found at position", poll_pos)
    after = code[poll_pos:]
    handlers = re.findall(r"@bot\.message_handler\(commands=\['(\w+)'\]\)", after)
    if handlers:
        print(f"Handlers AFTER polling: {handlers}")
    else:
        print("No handlers after polling")
else:
    print("No polling line found!")

print("\n=== 4. f-string issue ===")
if 'p["name"]' in code or "p[\"name\"]" in code:
    print("Problematic f-string still present, fixing...")
    code = code.replace('p["name"]', "p['name']").replace("p[\"name\"]", "p['name']")
    with open("bot.py","w") as f:
        f.write(code)
    print("Fixed.")
else:
    print("f-string looks clean.")

print("\n=== 5. Fix handlers order & ensure polling ===")
if "bot.infinity_polling" not in code and "bot.polling" not in code:
    code = code.replace("while True:", "bot.infinity_polling()\nwhile True:")
    print("Added bot.infinity_polling()")
poll_pos = code.find("bot.infinity_polling") if "bot.infinity_polling" in code else code.find("bot.polling")
if poll_pos != -1:
    after = code[poll_pos:]
    blocks = re.findall(r"(@bot\.message_handler\(commands=\[.*?\]\).*?)(?=\n@bot|\n\ndef|\Z)", after, re.DOTALL)
    if blocks:
        for b in blocks:
            code = code.replace(b, "")
        code = code.replace("bot.infinity_polling", "\n".join(blocks) + "\nbot.infinity_polling")
        print(f"Moved {len(blocks)} handlers before polling")
    else:
        print("No handlers to move")
else:
    print("Still no polling line after fix attempt!")
with open("bot.py","w") as f:
    f.write(code)

print("\n=== 6. Token test ===")
m = re.search(r'TOKEN\s*=\s*["\']([^"\']+)["\']', code)
if m:
    token = m.group(1)
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe").read()
        data = json.loads(resp)
        if data.get("ok"):
            print(f"Token valid. Bot: {data['result']['username']}")
        else:
            print("Token invalid!")
    except Exception as e:
        print(f"Could not test token: {e}")
else:
    print("Could not extract token from bot.py")

print("\n=== 7. Restart ===")
subprocess.run(["pkill", "-f", "python.*bot.py"], stderr=subprocess.DEVNULL)
import time; time.sleep(2)
subprocess.run(["./slh_daemon.sh"])
print("Done. Try /diagnose in Telegram.")
