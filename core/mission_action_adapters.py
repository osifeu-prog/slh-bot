"""Concrete allowlisted mission action adapters.

Adapters call existing domain authorities. They do not expose shell access or
arbitrary Python execution to mission payloads.
"""

from core import academy_manager


def execute_academy_complete_stage(*, payload, context, mission_id, idempotency_key):
    """Complete one Academy stage for the trusted mission owner."""
    uid = context.get("owner_id")
    if uid is None or str(uid).strip() == "":
        return {"verified": False, "error": "missing_trusted_owner"}

    course_id = payload.get("course_id")
    stage = payload.get("stage")
    if not course_id or stage is None:
        return {"verified": False, "error": "invalid_academy_payload"}

    result = academy_manager.complete_stage(
        str(uid),
        str(course_id),
        stage,
    )

    if not isinstance(result, dict) or not result.get("ok"):
        return {
            "verified": False,
            "error": result.get("error", "academy_stage_not_completed")
            if isinstance(result, dict)
            else "academy_stage_not_completed",
            "evidence": {"academy_result": result},
        }

    return {
        "verified": True,
        "evidence": {
            "authority": "core.academy_manager.complete_stage",
            "uid": str(uid),
            "course_id": str(course_id),
            "stage": int(stage),
            "academy_result": result,
            "idempotency_key": str(idempotency_key),
            "mission_id": str(mission_id),
        },
    }
