"""Owner command for Academy release-date announcements."""

from __future__ import annotations

from core import academy_manager
from core import academy_release
from core.identity import OWNER_TELEGRAM_ID


def register(bot):
    @bot.message_handler(commands=["academy_announce"])
    def academy_announce(m):
        if int(m.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(m, "⛔ OWNER only")
            return

        parts = (m.text or "").split(maxsplit=3)
        if len(parts) < 4:
            bot.reply_to(
                m,
                "Usage: /academy_announce <course_id> <stage> <release date/text>",
            )
            return

        course_id = parts[1].strip()
        try:
            stage = int(parts[2])
        except ValueError:
            bot.reply_to(m, "❌ stage must be a number")
            return
        release_text = parts[3].strip()

        course = academy_manager.get_courses().get(course_id) or {}
        if not course:
            bot.reply_to(m, "❌ course not found")
            return
        stage_data = next(
            (
                item for item in course.get("stages", [])
                if int(item.get("id", -1)) == stage
            ),
            None,
        )
        if not stage_data:
            bot.reply_to(m, "❌ lesson not found")
            return

        result = academy_release.announce_to_all_groups(
            bot,
            course.get("title", course_id),
            stage,
            release_text,
        )
        bot.reply_to(
            m,
            "✅ Academy announcement complete.
"
            f"Course: {course.get('title', course_id)}
"
            f"Lesson: {stage}
"
            f"Targets: {result['total_targets']}
"
            f"Sent: {result['sent']}
"
            f"Failed: {len(result['failed'])}",
        )
