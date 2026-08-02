import os
import shutil
import datetime

stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

target=f"state/snapshots/{stamp}"

os.makedirs(target,exist_ok=True)

for f in [
"state/db.json",
"state/agents.json",
"state/tasks.json",
"state/chats.json",
"state/ai_health.json"
]:
    if os.path.exists(f):
        shutil.copy2(
            f,
            target
        )

print("SNAPSHOT CREATED")
print(target)
