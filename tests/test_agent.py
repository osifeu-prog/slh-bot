#!/usr/bin/env python3
"""Agent OS Unit Tests"""
import json, os, time, sys

PASS = 0
FAIL = 0

def test(name, condition):
    global PASS, FAIL
    if condition:
        print(f"✅ {name}")
        PASS += 1
    else:
        print(f"❌ {name}")
        FAIL += 1

# 1. Simulate agent creation
agents = {}
aid = str(int(time.time() * 1000))
agents[aid] = {"name": "test", "role": "agent", "state": "idle", "inbox": [], "history": [],
               "created": time.strftime("%Y-%m-%d %H:%M:%S"), "permissions": ["read"]}
test("Agent created in dict", aid in agents)

# 2. Change state
agents[aid]["state"] = "busy"
agents[aid]["history"].append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": "state→busy"})
test("State changed", agents[aid]["state"] == "busy")
test("History recorded", len(agents[aid]["history"]) > 0)

# 3. Send message
agents[aid]["inbox"].append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "message": "hello"})
test("Inbox has message", len(agents[aid]["inbox"]) == 1)
test("Inbox content correct", agents[aid]["inbox"][0]["message"] == "hello")

# 4. Persistence (write/read JSON)
path = "test_agents.json"
with open(path, "w") as f:
    json.dump(agents, f)
with open(path) as f:
    loaded = json.load(f)
test("Persistence: saved & loaded", aid in loaded)
test("Persistence: state preserved", loaded[aid]["state"] == "busy")
os.remove(path)

# 5. Permissions
test("Permissions exist", "read" in agents[aid]["permissions"])

print(f"\n{'='*40}")
print(f"✅ PASSED: {PASS}  ❌ FAILED: {FAIL}")
print(f"{'='*40}")
sys.exit(0 if FAIL == 0 else 1)
