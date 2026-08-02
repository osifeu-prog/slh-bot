import json
from datetime import datetime, timezone
from pathlib import Path


AUDIT_PATH = Path("state/audit.jsonl")


def log_event(
    event,
    actor=None,
    target=None,
    details=None,
):
    """
    Append one structured audit event.

    The logger is intentionally:
    - append-only
    - JSONL-based
    - dependency-free
    - non-throwing for normal runtime failures
    """

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": str(event),
    }

    if actor is not None:
        record["actor"] = str(actor)

    if target is not None:
        record["target"] = str(target)

    if details is not None:
        record["details"] = details

    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)

        with AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

        return True

    except Exception:
        # Audit must never crash the primary application flow.
        return False


def read_events(limit=20):
    """
    Read the newest audit events.
    """

    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 20

    if not AUDIT_PATH.exists():
        return []

    try:
        with AUDIT_PATH.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        events = []

        for line in lines[-limit:]:
            line = line.strip()

            if not line:
                continue

            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return events

    except Exception:
        return []


def count_events():
    if not AUDIT_PATH.exists():
        return 0

    try:
        with AUDIT_PATH.open("r", encoding="utf-8") as f:
            return sum(
                1
                for line in f
                if line.strip()
            )

    except Exception:
        return 0
