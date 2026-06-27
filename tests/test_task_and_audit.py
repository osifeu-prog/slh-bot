#!/usr/bin/env python3
"""Test Task creation + Audit logging"""
import sys, os, time, json

# Add project root to path
sys.path.insert(0, '.')

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

# 1. Test audit_logger
print("[1] Audit Logger")
from audit_logger import audit, get_audit

# Clear old test entries (we'll just append and check our entry)
test_user = "test_user"
audit("test_action", test_user, "test_details")
entries = get_audit(5)
found = any(e.get("action") == "test_action" for e in entries)
test("Audit records action", found)

# 2. Test TaskPlugin + EventBus
print("\n[2] Task Plugin + EventBus")
from core.event_bus import EventBus
from plugins.task import TaskPlugin

bus = EventBus(workers=1)
# Manually set state on bus for compatibility (TaskPlugin expects k.state)
bus.state = {}
TaskPlugin().on_start(bus)

# Emit task_create
bus.emit("task_create", {"chat": 123, "task": "test_task_1"})
# Process events (since we are not running worker threads, we need to process manually)
# We'll directly check the state that TaskPlugin should have set
# However, TaskPlugin registers a handler that modifies k.state, but k is the object passed to on_start (which is bus in this case)
# So after emitting, we need to let the event be processed. Since we aren't running the worker loop, we manually call the handler.
# But we can't easily do that. Let's instead just test that the handler works by calling the handler directly.
# We'll simulate what the worker does: fetch pending event and process.
event = bus.store.fetch_batch(1)
if event:
    eid, etype, payload = event[0]
    bus._process(eid, etype, json.loads(payload))
    test("Task creation processed", "test_task_1" in bus.state.get("tasks", []))
else:
    test("Task creation processed", False)

# Emit another task and process
bus.emit("task_create", {"chat": 123, "task": "test_task_2"})
event = bus.store.fetch_batch(1)
if event:
    eid, etype, payload = event[0]
    bus._process(eid, etype, json.loads(payload))
    test("Second task processed", len(bus.state.get("tasks", [])) == 2)
else:
    test("Second task processed", False)

# Test task_list (just check no crash)
try:
    bus.emit("task_list", {"chat": 123})
    event = bus.store.fetch_batch(1)
    if event:
        eid, etype, payload = event[0]
        bus._process(eid, etype, json.loads(payload))
    test("Task list handler works", True)
except Exception as e:
    test("Task list handler works", False)

print(f"\n{'='*40}")
print(f"✅ PASSED: {PASS}  ❌ FAILED: {FAIL}")
print(f"{'='*40}")
sys.exit(0 if FAIL == 0 else 1)
