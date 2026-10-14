from unittest.mock import patch


def test_course_building_questions_are_not_misrouted_to_catalog():
    from core import ask_router

    assert ask_router.detect_intent("אני רוצה לבנות קורס מסחר חדש") == "general"
    assert ask_router.detect_intent("איך מעלים קורס מסחר לאוויר?") == "general"
    assert ask_router.detect_intent("אילו קורסים קיימים באקדמיה?") == "courses"


def test_live_system_status_question_does_not_fall_through_to_llm():
    from core import ask_router

    with patch.object(ask_router, "guard", return_value=True), patch.object(
        ask_router,
        "query_llm_with_context",
        side_effect=AssertionError("live status must not be guessed by the LLM"),
    ):
        answer = ask_router.route("מה מצב המערכת?", uid="test-user")

    assert "לא אסיק מצב חי מהקשר חלקי" in answer
    assert "/e alpha_status" in answer
    assert "PASS/FAIL/UNKNOWN" in answer


def test_asset_readiness_questions_are_classified_as_live_status():
    from core import ask_router

    assert ask_router.is_system_state_question("מה מצב BNB?")
    assert ask_router.is_system_state_question("האם המסחר הפנימי פתוח?")
    assert ask_router.is_system_state_question("סטטוס המערכת")
    assert not ask_router.is_system_state_question("איך עובד מסחר אלגוריתמי?")
