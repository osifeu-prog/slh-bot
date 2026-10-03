"""Small, privacy-safe product telemetry adapter.

Telemetry is a best-effort side effect. Business flows must not depend on it.
Events are persisted through the canonical audit writer; this module owns the
product event contract and rejects fields outside the allowlist.
"""

from datetime import datetime, timezone

from core.audit import log_event


_ALLOWED_RESULTS = {"started", "success", "blocked", "failed", "duplicate", "cancelled"}
_ALLOWED_FIELDS = {
    "event",
    "actor_key",
    "flow",
    "surface",
    "result",
    "reason",
    "journey_id",
    "duration_ms",
    "environment",
    "app_version",
}
_REQUIRED_FIELDS = {"event", "actor_key", "flow", "surface", "result", "journey_id"}

# Deliberately bounded: these are taxonomy values, not arbitrary user input.
_MAX_REASON = 80
_MAX_EVENT = 120
_MAX_ACTOR = 120
_MAX_JOURNEY = 80
_MAX_VERSION = 120


def _clean_text(value, maximum):
    if value is None:
        return None
    value = str(value).strip()
    if not value or len(value) > maximum:
        return None
    return value


def emit(
    *,
    event,
    actor_key,
    flow,
    surface,
    result,
    reason=None,
    journey_id,
    duration_ms=None,
    environment="production",
    app_version=None,
):
    """Emit one validated product event without affecting the business flow."""
    try:
        clean = {
            "event": _clean_text(event, _MAX_EVENT),
            "actor_key": _clean_text(actor_key, _MAX_ACTOR),
            "flow": _clean_text(flow, 60),
            "surface": _clean_text(surface, 40),
            "result": _clean_text(result, 20),
            "reason": _clean_text(reason, _MAX_REASON),
            "journey_id": _clean_text(journey_id, _MAX_JOURNEY),
            "environment": _clean_text(environment, 40),
            "app_version": _clean_text(app_version, _MAX_VERSION),
        }

        if any(clean.get(key) is None for key in _REQUIRED_FIELDS):
            return False
        if clean["result"] not in _ALLOWED_RESULTS:
            return False

        if duration_ms is not None:
            try:
                duration_ms = max(0, int(duration_ms))
            except (TypeError, ValueError):
                duration_ms = None
        if duration_ms is not None:
            clean["duration_ms"] = duration_ms

        details = {k: v for k, v in clean.items() if k != "event" and v is not None}
        # No message text, names, wallet/payment identifiers, balances, or raw
        # callback data are accepted by this contract.
        return bool(
            log_event(
                clean["event"],
                actor=clean["actor_key"],
                details=details,
            )
        )
    except Exception:
        return False
