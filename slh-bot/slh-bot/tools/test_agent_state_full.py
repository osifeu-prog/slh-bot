#!/usr/bin/env python3

import json
import hashlib
import tempfile
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent

# Ensure project root is importable when script runs from tools/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.agent_registry as registry
from core.agent_state_store import AgentStateStore


ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "state" / "db.json"
SNAPSHOT = ROOT / "state" / "agents.json"


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def snapshot():
    return {
        "db": sha256(DB),
        "snapshot": sha256(SNAPSHOT),
    }


def show(label, data):
    print()
    print("=" * 80)
    print(label)
    print("=" * 80)
    print(json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
        default=str,
    ))


def assert_sync(store):
    audit = store.audit()

    if not audit["ok"]:
        raise AssertionError(
            f"STATE DRIFT DETECTED: {audit}"
        )

    print("✅ DB ↔ SNAPSHOT synchronized")


def main():

    print("=" * 80)
    print("SLH AGENT STATE SYSTEM — FULL CRUD INTEGRATION TEST")
    print("=" * 80)

    store = AgentStateStore()

    print()
    print("INITIAL STATE")

    before = snapshot()

    print("Agents:", len(store.get_all()))
    print("Hashes:", before)

    assert_sync(store)

    original_ids = set(
        store.get_all().keys()
    )

    temp_id = None

    try:

        # -------------------------------------------------
        # CREATE
        # -------------------------------------------------

        print()
        print("[1/7] CREATE TEMPORARY AGENT")

        temp_id, created = registry.create_agent(
            "__STATE_TEST_AGENT__",
            role="test"
        )

        print(
            "✅ Created:",
            temp_id,
            created.get("name")
        )

        assert temp_id in store.get_all()
        assert_sync(store)

        # -------------------------------------------------
        # READ
        # -------------------------------------------------

        print()
        print("[2/7] READ")

        by_id = registry.get_agent(
            temp_id
        )

        by_name = registry.get_agent(
            "__STATE_TEST_AGENT__"
        )

        assert by_id[0] == temp_id
        assert by_name[0] == temp_id

        print("✅ Lookup by ID works")
        print("✅ Lookup by name works")

        # -------------------------------------------------
        # UPDATE
        # -------------------------------------------------

        print()
        print("[3/7] UPDATE")

        updated_id, updated = registry.update_agent(
            temp_id,
            state="active",
            test_marker="updated"
        )

        assert updated_id == temp_id
        assert updated["state"] == "active"
        assert updated["test_marker"] == "updated"

        print("✅ Update works")

        assert_sync(store)

        # -------------------------------------------------
        # STATE API
        # -------------------------------------------------

        print()
        print("[4/7] STATE STORE API")

        result = store.update_state(
            temp_id,
            "error"
        )

        print(result)

        assert result["new_state"] == "error"
        assert store.get(temp_id)["state"] == "error"

        print("✅ State update works")
        assert_sync(store)

        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

        print()
        print("[5/7] MESSAGE")

        message = "state-store-integration-test"

        sent_id = registry.send_message(
            temp_id,
            message
        )

        assert sent_id == temp_id

        inbox = registry.get_inbox(
            temp_id
        )

        assert message in inbox

        print("✅ Message delivery works")
        assert_sync(store)

        # -------------------------------------------------
        # INVALID STATE
        # -------------------------------------------------

        print()
        print("[6/7] INVALID STATE PROTECTION")

        failed = False

        try:
            store.update_state(
                temp_id,
                "INVALID_STATE"
            )

        except ValueError:
            failed = True
            print(
                "✅ Invalid state rejected"
            )

        assert failed

        # Verify no corruption
        current = store.get(
            temp_id
        )

        assert current["state"] == "error"

        print(
            "✅ Invalid operation did not corrupt state"
        )

        assert_sync(store)

    finally:

        # -------------------------------------------------
        # DELETE / CLEANUP
        # -------------------------------------------------

        print()
        print("[7/7] CLEANUP")

        if temp_id is not None:

            registry.delete_agent(
                temp_id
            )

            print(
                "✅ Temporary agent deleted"
            )

        assert_sync(store)

    # -----------------------------------------------------
    # FINAL INTEGRITY
    # -----------------------------------------------------

    after = snapshot()

    final_ids = set(
        store.get_all().keys()
    )

    print()
    print("=" * 80)
    print("FINAL INTEGRITY")
    print("=" * 80)

    print(
        "Original agents:",
        sorted(original_ids)
    )

    print(
        "Final agents:",
        sorted(final_ids)
    )

    assert original_ids == final_ids

    print(
        "✅ Agent set restored exactly"
    )

    final_audit = store.audit()

    assert final_audit["ok"]

    print(
        "✅ Final audit clean"
    )

    print()
    print("HASHES")

    print(
        "BEFORE:",
        before
    )

    print(
        "AFTER :",
        after
    )

    print()
    print("=" * 80)
    print("FULL CRUD TEST PASSED")
    print("=" * 80)

    print()
    print("RESULT:")
    print("✅ CREATE")
    print("✅ READ")
    print("✅ UPDATE")
    print("✅ STATE TRANSITION")
    print("✅ MESSAGE")
    print("✅ INVALID INPUT PROTECTION")
    print("✅ DELETE")
    print("✅ SNAPSHOT SYNC")
    print("✅ FINAL STATE RESTORED")
    print("✅ NO BOT RESTART")
    print()


if __name__ == "__main__":
    main()
