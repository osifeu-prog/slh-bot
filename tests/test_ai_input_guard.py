import unittest
from unittest.mock import patch

from core.ask_router import AI_INPUT_TOO_LONG_MESSAGE, route


class AiInputGuardTests(unittest.TestCase):
    def test_long_wallet_question_stays_deterministic(self):
        question = "כמה Credits יש לי כרגע, ומה היתרה שלי?" + (" " * 1500)
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.get_balance_safe", return_value=8.5):
                with patch("core.ask_router.query_llm_with_context") as llm:
                    result = route(question, uid="100")
        self.assertIn("8.5", result)
        llm.assert_not_called()

    def test_long_general_input_is_chunked_before_llm(self):
        captured = {}

        def fake_llm(question, uid=None):
            captured["question"] = question
            return "OK"

        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context", side_effect=fake_llm):
                result = route("x" * 1501, uid="100")

        self.assertEqual(result, "OK")
        self.assertIn("[AI_INPUT_CHUNK 1/2]", captured["question"])
        self.assertIn("[AI_INPUT_CHUNK 2/2]", captured["question"])
        self.assertEqual(captured["question"].count("x"), 1501)

    def test_over_bound_input_is_rejected_before_llm(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context") as llm:
                result = route("x" * 12001, uid="100")
        self.assertEqual(result, AI_INPUT_TOO_LONG_MESSAGE)
        llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
