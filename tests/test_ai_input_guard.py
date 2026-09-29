import unittest
from unittest.mock import patch

from core.ask_router import AI_INPUT_TOO_LONG_MESSAGE, route


class AiInputGuardTests(unittest.TestCase):
    def test_input_over_telegram_limit_is_rejected_before_llm(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context") as llm:
                result = route("x" * 4097, uid="100")
        self.assertEqual(result, AI_INPUT_TOO_LONG_MESSAGE)
        llm.assert_not_called()

    def test_input_between_old_and_new_limit_reaches_llm(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context", return_value="OK"):
                result = route("x" * 1501, uid="100")
        self.assertEqual(result, "OK")

    def test_new_boundary_input_is_not_rejected(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context", return_value="OK"):
                result = route("x" * 4096, uid="100")
        self.assertEqual(result, "OK")


if __name__ == "__main__":
    unittest.main()
