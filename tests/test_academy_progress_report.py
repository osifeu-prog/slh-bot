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

    def reply_to(self, message, text, reply_markup=None):
        self.replies.append((message, text, reply_markup))


def test_academy_progress_is_hebrew_and_derived_from_canonical_course_state():
    bot = _Bot()
    msg = SimpleNamespace(text="/academy_progress", from_user=SimpleNamespace(id=8789977826))
    state = {
        "bitcoin_mastery": {"stage": 2, "completed": [1, 2, 99], "active": True},
        "music_theory_foundations": {"stage": 1, "completed": [1], "active": False},
    }
    catalog = {
        "bitcoin_mastery": {
            "title": "ביטקוין מאסטרי",
            "stages": [{"id": 1}, {"id": 2}, {"id": 3}],
        },
        "music_theory_foundations": {
            "title": "תאוריה מוזיקלית",
            "stages": [{"id": 1}, {"id": 2}],
        },
    }
    original_state = {key: dict(value) for key, value in state.items()}

    with (
        patch.object(academy_handler.academy_manager, "progress", return_value=state),
        patch.object(academy_handler.academy_manager, "get_courses", return_value=catalog),
        patch.object(
            academy_handler.profile_manager,
            "get_user",
            return_value={"gamification": {"points": 125, "level": 2}},
        ),
    ):
        academy_handler.register(bot)
        bot.handlers[("academy_progress",)](msg)

    assert len(bot.replies) == 1
    report = bot.replies[0][1]
    assert "דוח ההתקדמות הלימודית שלך" in report
    assert "נקודות מערכת: 125" in report
    assert "רמה: 2" in report
    assert "ביטקוין מאסטרי" in report
    assert "2/3 שיעורים (67%)" in report
    assert "תאוריה מוזיקלית" in report
    assert "1/2 שיעורים (50%)" in report
    assert "סה״כ בקורסים שלך: 3/5 שיעורים (60%)" in report
    assert "אין כאן שדה נפרד בשם hebrew_score" in report
    assert state == original_state


def test_academy_progress_does_not_invent_courses_when_none_are_started():
    bot = _Bot()
    msg = SimpleNamespace(text="/academy_progress", from_user=SimpleNamespace(id=8789977826))

    with (
        patch.object(academy_handler.academy_manager, "progress", return_value={}),
        patch.object(academy_handler.academy_manager, "get_courses") as get_courses,
        patch.object(academy_handler.profile_manager, "get_user") as get_user,
    ):
        academy_handler.register(bot)
        bot.handlers[("academy_progress",)](msg)

    report = bot.replies[0][1]
    assert "עדיין אין קורסים עם התקדמות שמורה" in report
    assert "42/42" not in report
    assert "7/7" not in report
    get_courses.assert_not_called()
    get_user.assert_not_called()
