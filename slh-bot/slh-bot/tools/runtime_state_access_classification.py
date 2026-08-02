#!/usr/bin/env python3

import ast
import json
import re
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent.parent

MAP_FILE = (
    ROOT
    / "state"
    / "takeover"
    / "runtime_state_dependency_map.json"
)

OUTPUT = (
    ROOT
    / "state"
    / "takeover"
    / "runtime_state_access_classification.json"
)


def now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def load_map():

    if not MAP_FILE.exists():

        raise FileNotFoundError(
            f"Runtime map not found: {MAP_FILE}"
        )

    return json.loads(
        MAP_FILE.read_text(
            encoding="utf-8"
        )
    )


def read_source(path):

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )


def detect_domains(path, text):

    domains = set()

    rel = str(
        path.relative_to(ROOT)
    )

    lower = text.lower()

    # -------------------------------------------------
    # AGENT STATE
    # -------------------------------------------------

    if (
        "agent_state_store" in lower
        or "agents.json" in lower
        or "db.get(\"agents\"" in lower
        or "db.get('agents'" in lower
        or "agents = db" in lower
        or "agent_registry" in lower
    ):

        domains.add(
            "AGENT_STATE"
        )

    # -------------------------------------------------
    # USER STATE
    # -------------------------------------------------

    if (
        "users" in lower
        or "profile" in lower
        or "user_id" in lower
        or "telegram_id" in lower
    ):

        domains.add(
            "USER_STATE"
        )

    # -------------------------------------------------
    # ASK / CONTEXT
    # -------------------------------------------------

    if (
        "ask" in rel.lower()
        or "context" in rel.lower()
        or "llm" in rel.lower()
        or "systemcollector" in lower
        or "system_collector" in lower
    ):

        domains.add(
            "ASK_CONTEXT"
        )

    # -------------------------------------------------
    # CONFIG
    # -------------------------------------------------

    if (
        "config" in lower
        or "settings" in lower
        or "token" in lower
        or "db_file" in lower
    ):

        domains.add(
            "CONFIG"
        )

    # -------------------------------------------------
    # AUDIT / LOG
    # -------------------------------------------------

    if (
        "audit" in rel.lower()
        or "audit" in lower
        or "log_event" in lower
        or "audit.log" in lower
    ):

        domains.add(
            "AUDIT_LOG"
        )

    # -------------------------------------------------
    # EVENT SERIALIZATION
    # -------------------------------------------------

    if (
        "json.dumps" in lower
        or "json.loads" in lower
        or "event_store" in rel.lower()
        or "payload" in lower
    ):

        domains.add(
            "EVENT_SERIALIZATION"
        )

    # -------------------------------------------------
    # GLOBAL DB
    # -------------------------------------------------

    if (
        "state/db.json" in lower
        or "db_path" in lower
        or "db_file" in lower
    ):

        domains.add(
            "GLOBAL_DB"
        )

    if not domains:

        domains.add(
            "UNKNOWN"
        )

    return sorted(
        domains
    )


def detect_access(findings, text):

    has_read = False
    has_write = False

    for finding in findings:

        code = finding.get(
            "code",
            ""
        )

        pattern = finding.get(
            "pattern",
            ""
        )

        if (
            "json.load" in code
            or "open(" in code
            and (
                '"r"' in code
                or "'r'" in code
                or "encoding=" in code
            )
            or "DB_PATH" in code
            or "SNAPSHOT_PATH" in code
        ):

            has_read = True

        if (
            "json.dump" in code
            or ".write_text" in code
            or ".write_bytes" in code
            or (
                "open(" in code
                and (
                    '"w"' in code
                    or "'w'" in code
                )
            )
        ):

            has_write = True

    # More reliable broad checks
    if re.search(
        r"json\.load\s*\(",
        text
    ):

        has_read = True

    if re.search(
        r"json\.dump\s*\(",
        text
    ):

        has_write = True

    if re.search(
        r"\.write_text\s*\(",
        text
    ):

        has_write = True

    if re.search(
        r"\.write_bytes\s*\(",
        text
    ):

        has_write = True

    if has_read and has_write:

        return "READ_WRITE"

    if has_write:

        return "WRITE"

    if has_read:

        return "READ"

    return "UNKNOWN"


def classify_priority(
    path,
    domains,
    access,
    is_gateway
):

    rel = str(
        path.relative_to(ROOT)
    )

    if is_gateway:

        return "CANONICAL"

    if rel == "bot_stable.py":

        return "CRITICAL"

    if (
        "GLOBAL_DB" in domains
        and access == "READ_WRITE"
    ):

        return "CRITICAL"

    if (
        "USER_STATE" in domains
        and access == "READ_WRITE"
    ):

        return "HIGH"

    if (
        "AGENT_STATE" in domains
        and access == "READ_WRITE"
    ):

        return "HIGH"

    if (
        "ASK_CONTEXT" in domains
        and access == "READ"
    ):

        return "MEDIUM"

    if (
        "AUDIT_LOG" in domains
        or "EVENT_SERIALIZATION" in domains
    ):

        return "LOW"

    return "MEDIUM"


def classify_scope(
    domains,
    path
):

    rel = str(
        path.relative_to(ROOT)
    )

    if (
        "AGENT_STATE" in domains
        and "GLOBAL_DB" not in domains
    ):

        return "AGENTS"

    if (
        "USER_STATE" in domains
    ):

        return "USERS"

    if (
        "ASK_CONTEXT" in domains
    ):

        return "ASK"

    if (
        "CONFIG" in domains
    ):

        return "CONFIG"

    if (
        "AUDIT_LOG" in domains
    ):

        return "AUDIT"

    if (
        "GLOBAL_DB" in domains
    ):

        return "GLOBAL_DB"

    return rel


def main():

    print("=" * 80)
    print(
        "SLH RUNTIME STATE ACCESS CLASSIFICATION"
    )
    print("=" * 80)

    data = load_map()

    runtime = data.get(
        "runtime_state_access",
        []
    )

    classifications = []

    for item in runtime:

        rel = item["path"]

        path = ROOT / rel

        if not path.exists():

            continue

        text = read_source(
            path
        )

        domains = detect_domains(
            path,
            text
        )

        access = detect_access(
            item.get(
                "findings",
                []
            ),
            text
        )

        is_gateway = bool(
            item.get(
                "is_gateway",
                False
            )
        )

        scope = classify_scope(
            domains,
            path
        )

        priority = classify_priority(
            path,
            domains,
            access,
            is_gateway
        )

        classifications.append(
            {
                "path": rel,
                "domains": domains,
                "scope": scope,
                "access": access,
                "is_gateway": is_gateway,
                "priority": priority,
                "finding_count": len(
                    item.get(
                        "findings",
                        []
                    )
                ),
            }
        )

    priority_order = {
        "CANONICAL": 0,
        "CRITICAL": 1,
        "HIGH": 2,
        "MEDIUM": 3,
        "LOW": 4,
    }

    classifications.sort(
        key=lambda x: (
            priority_order.get(
                x["priority"],
                99
            ),
            x["path"],
        )
    )

    result = {
        "generated_at": now(),
        "source_map": str(
            MAP_FILE.relative_to(ROOT)
        ),
        "source_of_truth": (
            "core.agent_state_store.AgentStateStore"
        ),
        "total_classified": len(
            classifications
        ),
        "classifications": classifications,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    print()
    print(
        "CLASSIFIED:",
        len(classifications)
    )

    print()
    print(
        "STATE GOVERNANCE MAP"
    )

    for item in classifications:

        print()
        print(
            f"[{item['priority']}]",
            item["path"]
        )

        print(
            "  DOMAIN:",
            ", ".join(
                item["domains"]
            )
        )

        print(
            "  SCOPE:",
            item["scope"]
        )

        print(
            "  ACCESS:",
            item["access"]
        )

        print(
            "  GATEWAY:",
            "YES"
            if item["is_gateway"]
            else "NO"
        )

    print()
    print(
        "OUTPUT:",
        OUTPUT
    )

    print()
    print("=" * 80)
    print(
        "CLASSIFICATION COMPLETE"
    )
    print(
        "READ-ONLY"
    )
    print(
        "NO RUNTIME FILES MODIFIED"
    )
    print(
        "NO RESTART"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
