import os
import re
from collections import defaultdict

commands = defaultdict(list)

for root, dirs, files in os.walk("."):
    if ".git" in root:
        continue

    for f in files:
        if f.endswith(".py"):
            path=os.path.join(root,f)

            try:
                data=open(path,encoding="utf-8",errors="ignore").read()

                matches=re.findall(
                    r"commands\s*=\s*\[([^\]]+)\]",
                    data
                )

                for m in matches:
                    cmds=re.findall(
                        r"['\"]([^'\"]+)['\"]",
                        m
                    )

                    for c in cmds:
                        commands[c].append(path)

            except:
                pass


print("\n===== DUPLICATE COMMANDS =====\n")

for cmd,files in sorted(commands.items()):
    if len(files)>1:
        print("/"+cmd)
        for f in files[:5]:
            print("  ",f)
        print()

print("\n===== TOTAL COMMANDS =====")
print(len(commands))
