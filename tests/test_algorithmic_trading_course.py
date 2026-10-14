import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_algorithmic_trading_course_is_registered_and_paid_in_stars():
    courses = json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))
    course = courses["algo_trading_999"]
    assert course["title"] == "מסחר אלגוריתמי, כוחות השוק ופסיכולוגיה"
    assert course["access"] == "paid"
    assert course["store_item"] == "course_algo_trading"
    assert [stage["id"] for stage in course["stages"]] == [1, 2, 3, 4, 5, 6]
    items = json.loads((ROOT / "store" / "items.json").read_text(encoding="utf-8"))
    item = items["course_algo_trading"]
    assert item["type"] == "course"
    assert item["stars_only"] is True
    assert item["price_stars"] == 299
    assert item["grant"]["course"] == "algo_trading_999"


def test_every_algorithmic_trading_lesson_exists_and_has_real_content():
    courses = json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))
    for stage in courses["algo_trading_999"]["stages"]:
        lesson = ROOT / stage["lesson"]
        assert lesson.is_file(), f"missing lesson {stage['id']}"
        content = lesson.read_text(encoding="utf-8").strip()
        assert len(content) >= 900, f"lesson {stage['id']} is only a stub"
        assert "תרגיל" in content or "פרויקט מסכם" in content
        assert "בדיקת הבנה" in content or "קריטריוני קבלה" in content


def test_exchange_chart_guide_explains_internal_trade_based_candles():
    html = (ROOT / "mini_app.html").read_text(encoding="utf-8")
    assert 'id="exchangeChartGuide"' in html
    assert "עסקאות פנימיות שהושלמו" in html
    assert "לא מחיר DEX" in html
    assert "לא לבצע הפקדה או עסקה אמיתית רק כדי לייצר נר" in html
