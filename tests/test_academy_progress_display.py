from types import SimpleNamespace
from unittest.mock import patch

from handlers import academy_handler


class _Bot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handlers[tuple(kwargs.get("commands", []))] = fn
            return fn
        return decorator

    def reply_to(self, message, text):
        self.replies.append((message, text))


def test_academy_progress_report_uses_course_catalog_and_hebrew_titles():
    bot = _Bot()
    message = SimpleNamespace(text="/academy_progress", from_user=SimpleNamespace(id=8789977826))
    progress = {
        "bitcoin_mastery": {"stage": 3, "completed": [1, 2], "active": True},
        "ai_tokens": {"stage": 2, "completed": [1, 2], "active": False},
    }
    catalog = {
        "bitcoin_mastery": {
            "title": "ביטקוין מאסטרי",
            "stages": [{"id": 1}, {"id": 2}, {"id": 3}],
        },
        "ai_tokens": {
            "name": "טוקנים ב-AI",
            "stages": [{"id": 1}, {"id": 2}],
        },
    }

    with patch.object(academy_handler.academy_manager, "progress", return_value=progress), patch.object(
        academy_handler.academy_manager, "get_courses", return_value=catalog
    ), patch.object(academy_handler.profile_manager, "get_user", return_value={"academy": {"courses": {}}}):
        academy_handler.register(bot)
        bot.handlers[("academy_progress",)](message)

    report = bot.replies[0][1]
    assert "ביטקוין מאסטרי: 2/3 שיעורים (67%)" in report
    assert "טוקנים ב-AI: 2/2 שיעורים (100%)" in report
    assert "סה״כ בקורסים הרשומים: 4/5 שיעורים (80%)" in report
    assert "שלב שמור: 3 | פעיל" in report
    assert "שלב שמור: 2 | לא פעיל" in report


def test_academy_progress_reports_stored_certification_without_inference():
    bot = _Bot()
    message = SimpleNamespace(text="/academy_progress", from_user=SimpleNamespace(id=8789977826))
    progress = {"algo_trading_999": {"stage": 7, "completed": [1, 2, 3, 4, 5, 6, 7], "active": True}}
    catalog = {"algo_trading_999": {"title": "מסחר אלגוריתמי", "stages": [{"id": i} for i in range(1, 8)]}}

    with patch.object(academy_handler.academy_manager, "progress", return_value=progress), patch.object(
        academy_handler.academy_manager, "get_courses", return_value=catalog
    ), patch.object(
        academy_handler.profile_manager,
        "get_user",
        return_value={"academy": {"courses": {"algo_trading_999": {"certification_passed_at": "2026-10-20T10:00:00Z"}}}},
    ):
        academy_handler.register(bot)
        bot.handlers[("academy_progress",)](message)

    report = bot.replies[0][1]
    assert "מסחר אלגוריתמי: 7/7 שיעורים (100%)" in report
    assert "הסמכה: עברה" in report
