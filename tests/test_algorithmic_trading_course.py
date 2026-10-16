import json
from pathlib import Path

from handlers.lesson_handler import _split_message

ROOT = Path(__file__).resolve().parents[1]


def test_algorithmic_trading_course_is_registered_and_paid_in_stars():
    courses = json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))
    course = courses["algo_trading_999"]
    assert course["title"] == "מסחר אלגוריתמי, כוחות השוק ופסיכולוגיה"
    assert course["access"] == "paid"
    assert course["store_item"] == "course_algo_trading"
    assert [stage["id"] for stage in course["stages"]] == [1, 2, 3, 4, 5, 6, 7]
    items = json.loads((ROOT / "store" / "items.json").read_text(encoding="utf-8"))
    item = items["course_algo_trading"]
    assert item["type"] == "course"
    assert item["stars_only"] is True
    assert item["price_stars"] == 150
    assert item["grant"]["course"] == "algo_trading_999"


def test_every_algorithmic_trading_lesson_exists_and_has_real_content():
    courses = json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))
    for stage in courses["algo_trading_999"]["stages"]:
        lesson = ROOT / stage["lesson"]
        assert lesson.is_file(), f"missing lesson {stage['id']}"
        content = lesson.read_text(encoding="utf-8").strip()
        words = len(content.split())
        assert words >= 1400, f"lesson {stage['id']} has only {words} words"
        assert "תרגיל" in content or "פרויקט מסכם" in content or "מעבדת סימולציה" in content
        assert "בדיקת הבנה" in content or "קריטריוני קבלה" in content


def test_lesson_text_is_split_into_telegram_safe_chunks():
    source = ("כותרת חשובה\n\n" + ("זו פסקה לימודית שמכילה מילים רבות. " * 140)) * 3
    chunks = _split_message(source)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 3500 for chunk in chunks)
    source_words = source.split()
    chunk_words = [word for chunk in chunks for word in chunk.split()]
    assert chunk_words == source_words


def test_exchange_chart_guide_explains_internal_trade_based_candles():
    html = (ROOT / "mini_app.html").read_text(encoding="utf-8")
    assert 'id="exchangeChartGuide"' in html
    assert "עסקאות פנימיות שהושלמו" in html
    assert "לא מחיר DEX" in html
    assert "לא לבצע הפקדה או עסקה אמיתית רק כדי לייצר נר" in html


def _mock_paid_course_access(monkeypatch, *, progress=None, user=None, owner=False):
    from core import academy_manager, authority, profile_manager

    monkeypatch.setattr(
        academy_manager,
        "get_courses",
        lambda: {"paid_course": {"access": "paid", "stages": [{"id": 1}]}},
    )
    monkeypatch.setattr(
        academy_manager,
        "get_course",
        lambda uid, course_id: progress or {},
    )
    monkeypatch.setattr(
        profile_manager,
        "user_exists",
        lambda uid: user is not None,
    )
    monkeypatch.setattr(
        profile_manager,
        "get_user",
        lambda uid: user or {},
    )
    monkeypatch.setattr(authority, "is_owner", lambda uid: owner)


def test_unpaid_user_cannot_read_or_complete_paid_course(monkeypatch):
    from core import academy_manager, lesson_engine

    _mock_paid_course_access(
        monkeypatch,
        progress={},
        user={"vip_access_until": 0},
        owner=False,
    )
    monkeypatch.setattr(
        academy_manager,
        "complete_stage",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("unpaid course completion must be blocked")
        ),
    )

    assert lesson_engine.has_course_access("unpaid-user", "paid_course") is False
    assert lesson_engine.can_access_lesson("unpaid-user", "paid_course", 1) is False
    result = lesson_engine.complete_lesson("unpaid-user", "paid_course", 1)
    assert result["ok"] is False
    assert result["error"] == "course_locked"


def test_enrolled_user_can_access_paid_course(monkeypatch):
    from core import lesson_engine

    _mock_paid_course_access(
        monkeypatch,
        progress={"stage": 0, "completed": []},
        user=None,
        owner=False,
    )

    assert lesson_engine.has_course_access("buyer", "paid_course") is True
    assert lesson_engine.can_access_lesson("buyer", "paid_course", 1) is True


def test_active_vip_can_access_paid_course(monkeypatch):
    import time
    from core import lesson_engine

    _mock_paid_course_access(
        monkeypatch,
        progress={},
        user={"vip_access_until": int(time.time()) + 3600},
        owner=False,
    )

    assert lesson_engine.has_course_access("vip-user", "paid_course") is True


def test_owner_can_access_paid_course(monkeypatch):
    from core import lesson_engine

    _mock_paid_course_access(
        monkeypatch,
        progress={},
        user=None,
        owner=True,
    )

    assert lesson_engine.has_course_access("owner", "paid_course") is True
