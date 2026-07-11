#!/usr/bin/env python3

import json
import os
from datetime import datetime

MEMORY="state/system_memory.json"
OUT="state/checkpoints"

os.makedirs(OUT, exist_ok=True)

with open(MEMORY,"r") as f:
    memory=json.load(f)

now=datetime.now().strftime("%Y%m%d_%H%M%S")

checkpoint={
    "timestamp": now,
    "type": "AUTONOMOUS_CHECKPOINT",
    "memory": memory
}

path=f"{OUT}/checkpoint_{now}.json"

with open(path,"w") as f:
    json.dump(checkpoint,f,indent=2,ensure_ascii=False)

print("✅ Memory checkpoint created:")
print(path)
