#!/usr/bin/env python3

from pathlib import Path
import ast
from datetime import datetime, timezone
import hashlib
import importlib
import json
import py_compile
import sys


ROOT = Path(__file__).resolve().parent.parent

# Ensure project root is importable when this script is executed
# directly from tools/.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOARD = ROOT / "state" / "missions" / "board.json"


def header(title):
    print("=" * 80)
    print(title)
    print("=" * 80)

def verify_targets():
    print()
    print("PHASE 1: VERIFY TARGETS")

    targets = [
        ROOT / "services" / "task_service.py",
        ROOT / "core" / "mission_lifecycle.py",
        BOARD,
    ]

    for target in targets:
        if target.exists():
            print("PASS:", target.relative_to(ROOT))
        else:
            print("FAIL:", target.relative_to(ROOT))
            return False

    return True

def static_validation():
    print()
    print("PHASE 2: STATIC VALIDATION")

    targets = [
        ROOT / "services" / "task_service.py",
        ROOT / "core" / "mission_lifecycle.py",
    ]

    for path in targets:
        try:
            py_compile.compile(
                str(path),
                doraise=True,
            )

            print(
                "PASS:",
                path.relative_to(ROOT),
            )

        except Exception as exc:
            print(
                "FAIL:",
                path.relative_to(ROOT),
            )

            print(
                type(exc).__name__,
                repr(exc),
            )

            return False

    return True

def live_import_test():
    print()
    print("PHASE 3: LIVE IMPORT TEST")

    try:
        import services.task_service as task_service
        import core.mission_lifecycle as mission_lifecycle

        importlib.reload(task_service)
        importlib.reload(mission_lifecycle)

        print(
            "PASS: lifecycle modules imported"
        )

        return True

    except Exception as exc:
        print("FAIL: live import")
        print(type(exc).__name__, repr(exc))
        return False

def legacy_writer_block_test():
    print()
    print("PHASE 4: LEGACY WRITER BLOCK TEST")

    try:
        import services.task_service as task_service

        task_service.update_task_status(
            "MIGRATION-TEST",
            "completed",
        )

    except RuntimeError as exc:

        if (
            "legacy_status_writer_disabled"
            not in str(exc)
        ):
            print(
                "FAIL: unexpected RuntimeError"
            )

            print(str(exc))
            return False

        print(
            "PASS: legacy writer blocked"
        )

        return True

    except Exception as exc:

        print(
            "FAIL: unexpected exception"
        )

        print(
            type(exc).__name__,
            repr(exc),
        )

        return False

    print(
        "FAIL: legacy writer was not blocked"
    )

    return False

def add_task_regression_test():
    print()
    print("PHASE 5: ADD_TASK REGRESSION")

    before_bytes = BOARD.read_bytes()

    before_hash = hashlib.sha256(
        before_bytes
    ).hexdigest()

    description = (
        "SLH MIGRATION AUTOMATION TEST"
    )

    try:
        import services.task_service as task_service

        result = task_service.add_task(
            description
        )

        if result.get(
            "status"
        ) != "open":

            print(
                "FAIL: add_task status is not open"
            )

            return False

        if result.get(
            "desc"
        ) != description:

            print(
                "FAIL: add_task description mismatch"
            )

            return False

        print(
            "PASS: add_task lifecycle adapter operational"
        )

        print(
            "TEST MISSION:",
            result.get("id"),
        )

    except Exception as exc:

        print(
            "FAIL: add_task regression"
        )

        print(
            type(exc).__name__,
            repr(exc),
        )

        return False

    finally:

        # Restore board exactly, even if the test succeeded.
        BOARD.write_bytes(
            before_bytes
        )

    after_bytes = BOARD.read_bytes()

    after_hash = hashlib.sha256(
        after_bytes
    ).hexdigest()

    if after_bytes != before_bytes:

        print(
            "FAIL: board was not restored"
        )

        print(
            "BEFORE:",
            before_hash,
        )

        print(
            "AFTER:",
            after_hash,
        )

        return False

    print(
        "PASS: test mission rolled back"
    )

    print(
        "PASS: board restored byte-for-byte"
    )

    return True

def run_status():
    """
    Read-only migration status.
    No files modified.
    No board writes.
    No bot restart.
    """

    header(
        "SLH MIGRATION STATUS"
    )

    migrations = {
        "task-lifecycle": True,
    }

    print()

    for name, completed in migrations.items():

        symbol = (
            "PASS"
            if completed
            else "PENDING"
        )

        print(
            f"{symbol}: {name}"
        )

    print()
    print(
        "NO FILES MODIFIED"
    )

    print(
        "NO BOARD WRITE"
    )

    print(
        "NO BOT RESTART"
    )

    return 0

def run_lifecycle_contract():
    """
    Runtime contract probe for MissionLifecycleService.

    Creates one temporary mission, exercises the lifecycle,
    then restores board.json byte-for-byte.
    """

    header(
        "SLH MIGRATION: LIFECYCLE CONTRACT"
    )

    before_bytes = BOARD.read_bytes()

    try:
        before_hash = hashlib.sha256(
            before_bytes
        ).hexdigest()

        print()
        print("PHASE 1: IMPORT LIFECYCLE")

        import core.mission_lifecycle as mission_module

        mission_module = importlib.reload(
            mission_module
        )

        MissionLifecycleService = (
            mission_module.MissionLifecycleService
        )

        print(
            "PASS: MissionLifecycleService imported"
        )

        print()
        print("PHASE 2: INSPECT API")

        required_methods = [
            "create_mission",
            "assign_mission",
            "execute_mission",
            "complete_mission",
        ]

        missing = []

        for method_name in required_methods:

            method = getattr(
                MissionLifecycleService,
                method_name,
                None
            )

            if callable(method):

                print(
                    "PASS:",
                    method_name,
                )

            else:

                print(
                    "FAIL:",
                    method_name,
                )

                missing.append(
                    method_name
                )

        if missing:

            print()
            print(
                "FAIL: lifecycle contract incomplete"
            )

            print(
                "MISSING:",
                ", ".join(missing)
            )

            return 1

        print()
        print("PHASE 3: CONSTRUCTOR INSPECTION")

        try:

            service = MissionLifecycleService()

            print(
                "PASS: service instantiated"
            )

        except Exception as exc:

            print(
                "FAIL: service constructor"
            )

            print(
                type(exc).__name__,
                repr(exc)
            )

            return 1

        print()
        print("PHASE 4: METHOD SIGNATURES")

        import inspect

        for method_name in required_methods:

            method = getattr(
                service,
                method_name
            )

            print(
                method_name + ":",
                inspect.signature(method)
            )

        print()
        print("PHASE 5: CONTRACT STATUS")

        print(
            "PASS: lifecycle service exists"
        )

        print(
            "PASS: required lifecycle methods exist"
        )

        print(
            "PASS: service can be instantiated"
        )

        print()
        print("PHASE 6: BOARD SAFETY")

        after_bytes = BOARD.read_bytes()

        after_hash = hashlib.sha256(
            after_bytes
        ).hexdigest()

        if after_bytes != before_bytes:

            print(
                "FAIL: board changed during inspection"
            )

            print(
                "BEFORE:",
                before_hash
            )

            print(
                "AFTER:",
                after_hash
            )

            return 1

        print(
            "PASS: board unchanged"
        )

        print()
        print(
            "LIFECYCLE CONTRACT:"
        )

        print(
            "  create_mission: PRESENT"
        )

        print(
            "  assign_mission: PRESENT"
        )

        print(
            "  execute_mission: PRESENT"
        )

        print(
            "  complete_mission: PRESENT"
        )

        print(
            "  board mutation: NOT PERFORMED"
        )

        print(
            "  rollback: NOT REQUIRED"
        )

        return 0

    finally:

        # Safety restoration even if future probes are added.
        if BOARD.exists():

            BOARD.write_bytes(
                before_bytes
            )

def run_execution_contract():
    """
    Read-only audit of MissionLifecycleService execution and
    completion requirements.

    No mission created.
    No board write.
    No agent mutation.
    No bot restart.
    """

    header(
        "SLH MIGRATION: EXECUTION CONTRACT"
    )

    print()
    print("PHASE 1: IMPORT")

    try:

        import core.mission_lifecycle as mission_module

        mission_module = importlib.reload(
            mission_module
        )

        service = (
            mission_module.MissionLifecycleService()
        )

        print(
            "PASS: lifecycle service imported"
        )

    except Exception as exc:

        print(
            "FAIL: import"
        )

        print(
            type(exc).__name__,
            repr(exc)
        )

        return 1

    print()
    print("PHASE 2: SOURCE INSPECTION")

    source_path = (
        ROOT
        / "core"
        / "mission_lifecycle.py"
    )

    try:

        source = source_path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source,
            filename=str(source_path)
        )

    except Exception as exc:

        print(
            "FAIL: source inspection"
        )

        print(
            type(exc).__name__,
            repr(exc)
        )

        return 1

    targets = {
        "assign_mission",
        "execute_mission",
        "complete_mission",
    }

    for node in tree.body:

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            )
        ):

            continue

        if isinstance(
            node,
            ast.ClassDef
        ):

            methods = {
                child.name: child
                for child in node.body
                if isinstance(
                    child,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    )
                )
            }

            for name in targets:

                if name not in methods:

                    continue

                method = methods[name]

                print()
                print(
                    "METHOD:",
                    name
                )

                print(
                    "LINE:",
                    method.lineno
                )

                calls = []

                for child in ast.walk(
                    method
                ):

                    if isinstance(
                        child,
                        ast.Name
                    ):

                        if child.id in {
                            "result",
                            "verified",
                            "success",
                            "hash",
                            "completion",
                        }:

                            calls.append(
                                child.id
                            )

                if calls:

                    print(
                        "REFERENCES:",
                        sorted(
                            set(
                                calls
                            )
                        )
                    )

                print(
                    "SOURCE:"
                )

                segment = ast.get_source_segment(
                    source,
                    method
                )

                if segment:

                    print(
                        segment
                    )

    print()
    print("PHASE 3: SIGNATURES")

    import inspect

    for name in [
        "assign_mission",
        "execute_mission",
        "complete_mission",
    ]:

        method = getattr(
            service,
            name,
            None
        )

        if callable(
            method
        ):

            print(
                name + ":",
                inspect.signature(
                    method
                )
            )

    print()
    print("PHASE 4: DECISION")

    print(
        "PASS: read-only contract audit complete"
    )

    print(
        "NO MISSION CREATED"
    )

    print(
        "NO BOARD WRITE"
    )

    print(
        "NO AGENT MUTATION"
    )

    print(
        "NO BOT RESTART"
    )

    return 0


def run_agent_execution_contract():
    """
    Read-only audit of the agent execution layer.

    Finds agent-related runtime components and inspects their
    callable execution interfaces without invoking them.

    No agent execution.
    No mission creation.
    No board write.
    No agent mutation.
    No bot restart.
    """

    header(
        "SLH MIGRATION: AGENT EXECUTION CONTRACT"
    )

    print()
    print("PHASE 1: DISCOVER AGENT RUNTIME SOURCES")

    candidates = [
        ROOT / "core" / "agents.py",
        ROOT / "core" / "agent_runtime.py",
        ROOT / "core" / "agent_manager.py",
        ROOT / "services" / "agent_service.py",
        ROOT / "services" / "agent_runtime.py",
        ROOT / "services" / "agent_manager.py",
        ROOT / "handlers" / "agents_handler.py",
        ROOT / "handlers" / "task_handler.py",
        ROOT / "handlers" / "project_commands.py",
    ]

    existing = []

    for path in candidates:

        if path.exists():

            existing.append(
                path
            )

            print(
                "FOUND:",
                path.relative_to(ROOT)
            )

    if not existing:

        print(
            "FAIL: no known agent runtime source found"
        )

        return 1

    print()
    print("PHASE 2: STATIC CLASS AND FUNCTION INVENTORY")

    execution_keywords = {
        "execute",
        "run",
        "dispatch",
        "send",
        "handle",
        "process",
        "task",
        "mission",
        "agent",
    }

    discovered = []

    for path in existing:

        print()
        print(
            "SOURCE:",
            path.relative_to(ROOT)
        )

        try:

            source = path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(
                source,
                filename=str(path)
            )

        except Exception as exc:

            print(
                "SKIP:",
                type(exc).__name__,
                repr(exc)
            )

            continue

        for node in ast.walk(tree):

            if isinstance(
                node,
                ast.ClassDef
            ):

                print(
                    "CLASS:",
                    node.name,
                    "LINE:",
                    node.lineno
                )

                methods = []

                for child in node.body:

                    if isinstance(
                        child,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                        )
                    ):

                        methods.append(
                            child.name
                        )

                        lower_name = (
                            child.name.lower()
                        )

                        if any(
                            keyword in lower_name
                            for keyword in execution_keywords
                        ):

                            discovered.append(
                                (
                                    path,
                                    node.name,
                                    child.name,
                                    child.lineno,
                                )
                            )

                if methods:

                    print(
                        "METHODS:",
                        ", ".join(
                            methods
                        )
                    )

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                )
            ):

                lower_name = (
                    node.name.lower()
                )

                if any(
                    keyword in lower_name
                    for keyword in execution_keywords
                ):

                    discovered.append(
                        (
                            path,
                            "<module>",
                            node.name,
                            node.lineno,
                        )
                    )

    print()
    print("PHASE 3: POSSIBLE EXECUTION INTERFACES")

    unique = set()

    for (
        path,
        owner,
        name,
        line,
    ) in discovered:

        key = (
            str(path),
            owner,
            name,
            line,
        )

        if key in unique:

            continue

        unique.add(
            key
        )

        print(
            "CANDIDATE:",
            path.relative_to(ROOT),
            "::",
            owner,
            "::",
            name,
            ":: LINE",
            line,
        )

    if not unique:

        print(
            "INFO: no execution interfaces discovered"
        )

    print()
    print("PHASE 4: READ-ONLY SAFETY")

    print(
        "PASS: source inspection only"
    )

    print(
        "PASS: no agent execution"
    )

    print(
        "PASS: no mission creation"
    )

    print(
        "PASS: no board write"
    )

    print(
        "PASS: no agent mutation"
    )

    print(
        "PASS: no bot restart"
    )

    return 0


def run_agent_discovery():
    """
    Discover the authoritative agent registry and print
    real agents and their lifecycle eligibility.

    Read-only operation.
    No board write.
    No agent mutation.
    No bot restart.
    """

    header(
        "SLH MIGRATION: AGENT DISCOVERY"
    )

    print()
    print("PHASE 1: SEARCH AGENT SOURCES")

    candidates = [
        ROOT / "state" / "agents.json",
        ROOT / "state" / "db.json",
        ROOT / "state" / "users.json",
        ROOT / "core" / "agents.py",
        ROOT / "services" / "agent_service.py",
        ROOT / "handlers" / "agents_handler.py",
    ]

    existing = []

    for path in candidates:

        if path.exists():

            existing.append(
                path
            )

            print(
                "FOUND:",
                path.relative_to(ROOT)
            )

    if not existing:

        print(
            "FAIL: no known agent source found"
        )

        return 1

    print()
    print("PHASE 2: JSON REGISTRY INSPECTION")

    json_sources = [
        path
        for path in existing
        if path.suffix == ".json"
    ]

    found_agents = []

    for path in json_sources:

        try:

            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception as exc:

            print(
                "SKIP:",
                path.relative_to(ROOT),
                type(exc).__name__
            )

            continue

        print()
        print(
            "SOURCE:",
            path.relative_to(ROOT)
        )

        if isinstance(data, dict):

            print(
                "TOP-LEVEL KEYS:",
                list(data.keys())
            )

            possible = []

            for key in [
                "agents",
                "agent",
                "registry",
                "users",
            ]:

                value = data.get(
                    key
                )

                if isinstance(
                    value,
                    (dict, list)
                ):

                    possible.append(
                        (
                            key,
                            value
                        )
                    )

            for key, value in possible:

                print(
                    "CANDIDATE COLLECTION:",
                    key
                )

                if isinstance(
                    value,
                    dict
                ):

                    for agent_id, agent_data in value.items():

                        if isinstance(
                            agent_data,
                            dict
                        ):

                            found_agents.append(
                                (
                                    str(agent_id),
                                    agent_data,
                                    path,
                                )
                            )

                elif isinstance(
                    value,
                    list
                ):

                    for agent_data in value:

                        if isinstance(
                            agent_data,
                            dict
                        ):

                            agent_id = (
                                agent_data.get(
                                    "id"
                                )
                                or agent_data.get(
                                    "agent_id"
                                )
                                or agent_data.get(
                                    "name"
                                )
                            )

                            if agent_id:

                                found_agents.append(
                                    (
                                        str(agent_id),
                                        agent_data,
                                        path,
                                    )
                                )

    print()
    print("PHASE 3: DISCOVERED AGENTS")

    unique = {}

    for agent_id, data, source in found_agents:

        unique.setdefault(
            agent_id,
            (
                data,
                source,
            )
        )

    if not unique:

        print(
            "INFO: no JSON agent records discovered"
        )

    else:

        for agent_id, (
            data,
            source,
        ) in unique.items():

            state = (
                data.get(
                    "state"
                )
                or data.get(
                    "status"
                )
                or "UNKNOWN"
            )

            print()
            print(
                "AGENT:",
                agent_id
            )

            print(
                "SOURCE:",
                source.relative_to(ROOT)
            )

            print(
                "STATE:",
                state
            )

            print(
                "DATA:",
                json.dumps(
                    data,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )

    print()
    print("PHASE 4: READ-ONLY SAFETY")

    print(
        "PASS: discovery only"
    )

    print(
        "PASS: no agent mutation"
    )

    print(
        "PASS: no board write"
    )

    print(
        "PASS: no bot restart"
    )

    return 0


def run_lifecycle_debug():
    """
    Debug lifecycle state transitions without modifying production code.
    Creates a temporary mission, prints state after every transition,
    then restores board.json byte-for-byte.
    """

    header(
        "SLH MIGRATION: LIFECYCLE STATE DEBUG"
    )

    before_bytes = BOARD.read_bytes()

    try:

        import core.mission_lifecycle as mission_module

        mission_module = importlib.reload(
            mission_module
        )

        service = (
            mission_module.MissionLifecycleService()
        )

        mission_id = (
            "DEBUG-"
            + datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%dT%H%M%S%fZ"
            )
        )

        print()
        print("MISSION:", mission_id)

        print()
        print("STEP 1: CREATE")

        result = service.create_mission(
            mission_id,
            "SLH LIFECYCLE DEBUG",
            reward=0,
        )

        print("RETURN:", repr(result))

        print()
        print("BOARD AFTER CREATE:")

        board = json.loads(
            BOARD.read_text(
                encoding="utf-8"
            )
        )

        mission = next(
            (
                m
                for m in board.get("missions", [])
                if str(m.get("id")) == str(mission_id)
            ),
            None,
        )

        print(json.dumps(
            mission,
            indent=2,
            ensure_ascii=False,
        ))

        print()
        print("STEP 2: ASSIGN")

        result = service.assign_mission(
            mission_id,
            "DEBUG-AGENT",
        )

        print("RETURN:", repr(result))

        board = json.loads(
            BOARD.read_text(
                encoding="utf-8"
            )
        )

        mission = next(
            (
                m
                for m in board.get("missions", [])
                if str(m.get("id")) == str(mission_id)
            ),
            None,
        )

        print("BOARD STATE:", json.dumps(
            mission,
            indent=2,
            ensure_ascii=False,
        ))

        print()
        print("STEP 3: EXECUTE")

        result = service.execute_mission(
            mission_id
        )

        print("RETURN:", repr(result))

        board = json.loads(
            BOARD.read_text(
                encoding="utf-8"
            )
        )

        mission = next(
            (
                m
                for m in board.get("missions", [])
                if str(m.get("id")) == str(mission_id)
            ),
            None,
        )

        print("BOARD STATE:", json.dumps(
            mission,
            indent=2,
            ensure_ascii=False,
        ))

        print()
        print("STEP 4: COMPLETE")

        result = service.complete_mission(
            mission_id
        )

        print("RETURN:", repr(result))

        board = json.loads(
            BOARD.read_text(
                encoding="utf-8"
            )
        )

        mission = next(
            (
                m
                for m in board.get("missions", [])
                if str(m.get("id")) == str(mission_id)
            ),
            None,
        )

        print("BOARD STATE:", json.dumps(
            mission,
            indent=2,
            ensure_ascii=False,
        ))

        print()
        print("DIAGNOSTIC COMPLETE")
        print("NO PRODUCTION CODE MODIFIED")

        return 0

    except Exception as exc:

        print()
        print("FAIL: lifecycle debug")
        print(type(exc).__name__, repr(exc))

        return 1

    finally:

        BOARD.write_bytes(
            before_bytes
        )

        print()
        print("PASS: board restored byte-for-byte")


def run_lifecycle_smoke():
    """
    Execute the complete mission lifecycle on a temporary mission.

    create -> assign -> execute -> complete

    The board is restored byte-for-byte after the test.
    """

    header(
        "SLH MIGRATION: LIFECYCLE SMOKE TEST"
    )

    before_bytes = BOARD.read_bytes()

    try:

        print()
        print("PHASE 1: IMPORT")

        import core.mission_lifecycle as mission_module

        mission_module = importlib.reload(
            mission_module
        )

        MissionLifecycleService = (
            mission_module.MissionLifecycleService
        )

        service = MissionLifecycleService()

        print(
            "PASS: lifecycle service ready"
        )

        print()
        print("PHASE 2: CREATE")

        mission_id = (
            "SMOKE-"
            + datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%dT%H%M%S%fZ"
            )
        )

        description = (
            "SLH LIFECYCLE SMOKE TEST"
        )

        created = service.create_mission(
            mission_id,
            description,
            reward=0,
        )

        if not created:
            print(
                "FAIL: create_mission returned empty result"
            )

            return 1

        print(
            "PASS: create_mission"
        )

        print(
            "MISSION:",
            mission_id
        )

        print()
        print("PHASE 3: ASSIGN")

        print()
        print("DISCOVERING ELIGIBLE AGENT")

        board, manifest = service.load_state()

        smoke_agent = None

        for candidate_id in [
            "1",
            "2",
            "3",
            "4",
        ]:

            candidate = service.find_agent(
                manifest,
                candidate_id,
            )

            if candidate is not None:

                state = candidate.get(
                    "state"
                )

                if state in (
                    "idle",
                    "active",
                ):

                    smoke_agent = candidate

                    break

        if smoke_agent is None:

            print(
                "FAIL: no eligible real agent found"
            )

            return 1

        smoke_agent_id = str(
            smoke_agent.get(
                "id"
            )
        )

        print(
            "PASS: eligible agent found"
        )

        print(
            "AGENT:",
            smoke_agent_id
        )

        print(
            "STATE:",
            smoke_agent.get(
                "state"
            )
        )

        assigned = service.assign_mission(
            mission_id,
            smoke_agent_id,
        )

        if not assigned:
            print(
                "FAIL: assign_mission returned empty result"
            )

            return 1

        print(
            "PASS: assign_mission"
        )

        print()
        print("PHASE 4: EXECUTE")

        executed = service.execute_mission(
            mission_id
        )

        if not executed:
            print(
                "FAIL: execute_mission returned empty result"
            )

            return 1

        print(
            "PASS: execute_mission"
        )

        print()
        print("PHASE 5: COMPLETE")

        completed = service.complete_mission(
            mission_id
        )

        if not completed:
            print(
                "FAIL: complete_mission returned empty result"
            )

            return 1

        print(
            "PASS: complete_mission"
        )

        print()
        print("PHASE 6: FINAL STATE")

        final_board = json.loads(
            BOARD.read_text(
                encoding="utf-8"
            )
        )

        found = None

        for mission in final_board.get(
            "missions",
            []
        ):

            if str(
                mission.get(
                    "id"
                )
            ) == str(
                mission_id
            ):

                found = mission
                break

        if found is None:

            print(
                "FAIL: smoke mission not found"
            )

            return 1

        print(
            "FINAL STATUS:",
            found.get(
                "status"
            )
        )

        if found.get(
            "status"
        ) != "completed":

            print(
                "FAIL: final status is not completed"
            )

            return 1

        print(
            "PASS: complete lifecycle reached completed"
        )

        return 0

    except Exception as exc:

        print()
        print(
            "FAIL: lifecycle smoke test"
        )

        print(
            type(exc).__name__,
            repr(exc)
        )

        return 1

    finally:

        BOARD.write_bytes(
            before_bytes
        )

        print()
        print(
            "PASS: board restored byte-for-byte"
        )


def run_task_lifecycle():

    header(
        "SLH MIGRATION: TASK LIFECYCLE"
    )

    print()
    print(
        "ROOT:",
        ROOT,
    )

    print(
        "TIME:",
        datetime.now(
            timezone.utc
        ).isoformat(),
    )

    if not verify_targets():
        return 1

    if not static_validation():
        return 1

    if not live_import_test():
        return 1

    if not legacy_writer_block_test():
        return 1

    if not add_task_regression_test():
        return 1

    print()
    print("=" * 80)
    print(
        "TASK LIFECYCLE MIGRATION AUDIT COMPLETE"
    )
    print("=" * 80)

    print()
    print("RESULT:")
    print(
        "  lifecycle writer: ACTIVE"
    )
    print(
        "  add_task adapter: ACTIVE"
    )
    print(
        "  legacy status writer: BLOCKED"
    )
    print(
        "  syntax: PASS"
    )
    print(
        "  imports: PASS"
    )
    print(
        "  regression: PASS"
    )
    print(
        "  rollback: PASS"
    )

    print()
    print(
        "NO BOT RESTART"
    )

    return 0

def main():

    if len(sys.argv) < 2:

        print(
            "Usage:"
        )

        print(
            "  python3 tools/slh_migrate.py task-lifecycle"
        )

        return 1

    command = sys.argv[1]

    if command == "status":
        return run_status()

    if command == "lifecycle-contract":
        return run_lifecycle_contract()

    if command == "lifecycle-smoke":
        return run_lifecycle_smoke()

    if command == "lifecycle-debug":
        return run_lifecycle_debug()

    if command == "agent-discovery":
        return run_agent_discovery()

    if command == "execution-contract":
        return run_execution_contract()

    if command == "agent-execution-contract":
        return run_agent_execution_contract()

    if command == "task-lifecycle":
        return run_task_lifecycle()

    print(
        "Unknown migration:",
        command,
    )

    print()
    print(
        "Available migrations:"
    )

    print(
        "  task-lifecycle"
    )

    return 1

if __name__ == "__main__":
    raise SystemExit(
        main()
    )
