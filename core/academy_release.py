"""Release announcements for Academy courses.

Read-only with respect to Academy progress: this module never edits user
balances or course progress. It can announce a course/lesson release to all
explicitly bound Telegram groups.
"""

from __future__ import annotations

from typing import Any

import state_manager


def get_stage(course_id: str, stage: int) -> dict[str, Any]:
    courses = state_manager.load_db().get("academy_catalog", {})
    course = courses.get(course_id)
    if isinstance(course, dict):
        for item in course.get("stages", []):
            try:
                if int(item.get("id")) == int(stage):
                    return item
            except (TypeError, ValueError):
                continue

    # Canonical catalog lives in courses.json; runtime DB is not the source
    # of Academy definitions. Import only as a fallback for compatibility.
    from core import academy_manager
    course = academy_manager.get_courses().get(course_id) or {}
    for item in course.get("stages", []):
        try:
            if int(item.get("id")) == int(stage):
                return item
        except (TypeError, ValueError):
            continue
    return {}


def bound_group_ids() -> list[str]:
    db = state_manager.load_db()
    groups = db.get("community_groups", {})
    if not isinstance(groups, dict):
        return []
    return [
        str(chat_id)
        for chat_id, group in groups.items()
        if isinstance(group, dict)
        and str(group.get("chat_id") or chat_id).strip()
        and group.get("role") in {"free", "vip", "academy"}
    ]


def render_release_notice(course_title: str, stage: int, release_text: str) -> str:
    return (
        "🎓 SLH Academy — עדכון שיעור

"
        f"📘 {course_title}
"
        f"➡️ שיעור {int(stage)}

"
        f"📅 {release_text}

"
        "העדכון נשלח לכל הקבוצות המקושרות ל-SLH Academy."
    )


def announce_to_all_groups(bot, course_title: str, stage: int, release_text: str) -> dict[str, Any]:
    message = render_release_notice(course_title, stage, release_text)
    sent = 0
    failed: list[dict[str, str]] = []

    for chat_id in bound_group_ids():
        try:
            bot.send_message(int(chat_id), message)
            sent += 1
        except Exception as exc:
            failed.append({
                "chat_id": chat_id,
                "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            })

    return {
        "ok": not failed,
        "sent": sent,
        "failed": failed,
        "total_targets": sent + len(failed),
    }
