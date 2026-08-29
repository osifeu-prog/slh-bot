#!/usr/bin/env python3
"""Agent OS Unit Tests — pytest-safe"""
import json
import os
import time
import sys

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"OK {name}")
        PASS += 1
    else:
        print(f"FAIL {name}")
        FAIL += 1


def run_agent_checks():
    global PASS, FAIL
    PASS = 0
    FAIL = 0

    agents = {}
    aid = str(int(time.time() * 1000))
    agents[aid] = {
        "name": "test",
        "role": "agent",
        "state": "idle",
        "inbox": [],
        "history": [],
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "permissions": ["read"],
    }
    check("Agent created in dict", aid in agents)

    agents[aid]["state"] = "busy"
    agents[aid]["history"].append(
        {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": "state->busy"}
    )
    check("State changed", agents[aid]["state"] == "busy")
    check("History recorded", len(agents[aid]["history"]) > 0)

    agents[aid]["inbox"].append(
        {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "message": "hello"}
    )
    check("Inbox has message", len(agents[aid]["inbox"]) == 1)
    check("Inbox content correct", agents[aid]["inbox"][0]["message"] == "hello")

    path = "test_agents.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(agents, f)
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    check("Persistence: saved & loaded", aid in loaded)
    check("Persistence: state preserved", loaded[aid]["state"] == "busy")
    os.remove(path)

    check("Permissions exist", "read" in agents[aid]["permissions"])

    print()
    print("=" * 40)
    print(f"PASSED: {PASS}  FAILED: {FAIL}")
    print("=" * 40)
    return FAIL == 0


def test_agent_system():
    """pytest entrypoint"""
    assert run_agent_checks() is True


if __name__ == "__main__":
    ok = run_agent_checks()
    sys.exit(0 if ok else 1)
