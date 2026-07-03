#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "[1] timeline module..."

cat > core/timeline.py << 'PY'
from core.db import DB
import json

class Timeline:
    def __init__(self):
        self.db = DB()

    def show(self, limit=20):
        events = self.db.get_events(limit)

        print("\n===== SWARM TIMELINE =====")
        for e in events:
            print(f"[{e['ts']:.0f}] {e['type']}")

            if isinstance(e['data'], dict):
                print("  data:", json.dumps(e['data'], ensure_ascii=False))
            else:
                print("  data:", e['data'])

        print("==========================\n")

    def replay(self, limit=10):
        events = self.db.get_events(limit)

        print("\n===== REPLAY MODE =====")
        for e in events:
            print("REPLAY >", e["type"], "->", e["data"])
        print("=======================\n")
PY

echo "[2] attach timeline to kernel..."

cat > patch_kernel_timeline.py << 'PY'
from core.timeline import Timeline

timeline = Timeline()

def attach(kernel):

    def log_timeline(data):
        # auto log every event into readable stream
        pass

    kernel.on("timeline.show", lambda d: timeline.show(d.get("limit", 20)))
    kernel.on("timeline.replay", lambda d: timeline.replay(d.get("limit", 10)))

    print("[TIMELINE ATTACHED]")
PY

echo "[3] loader helper..."

cat > enable_timeline.py << 'PY'
from patch_kernel_timeline import attach
from core.kernel import Kernel

def enable(kernel: Kernel):
    attach(kernel)
PY

echo "DONE ✔"
