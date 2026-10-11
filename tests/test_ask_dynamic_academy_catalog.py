from unittest.mock import patch


def test_ask_academy_answer_uses_canonical_course_catalog():
    from core import ask_router

    catalog = {
        "bitcoin_mastery": {
            "title": "ביטקוין מאסטרי",
            "access": "free",
            "stages": [{"id": i} for i in range(1, 13)],
        },
        "algorithmic_trading": {
            "title": "מסחר אלגוריתמי",
            "access": "paid",
            "store_item": "course_algorithmic_trading",
            "stages": [{"id": 1}, {"id": 2}],
        },
    }

    with patch.object(ask_router, "guard", return_value=True), patch(
        "core.academy_manager.get_courses", return_value=catalog
    ):
        answer = ask_router.route("אילו קורסים קיימים באקדמיה?", uid="test-user")

    assert "ביטקוין מאסטרי" in answer
    assert "12 שיעורים" in answer
    assert "מסחר אלגוריתמי" in answer
    assert "/course_algorithmic_trading" in answer
    assert "2 שיעורים" in answer
    assert "/lesson bitcoin_mastery 1" not in answer
