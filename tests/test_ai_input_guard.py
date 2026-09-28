import unittest
from unittest.mock import patch

from core.ask_router import AI_INPUT_TOO_LONG_MESSAGE, route


class AiInputGuardTests(unittest.TestCase):
    def test_input_above_legacy_1500_limit_is_sent_to_llm(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context", return_value="OK") as llm:
                result = route("x" * 1501, uid="100")
        self.assertEqual(result, "OK")
        llm.assert_called_once()

    def test_input_above_12000_limit_is_rejected_before_llm(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context") as llm:
                result = route("x" * 12001, uid="100")
        self.assertEqual(result, AI_INPUT_TOO_LONG_MESSAGE)
        llm.assert_not_called()

    def test_boundary_input_is_not_rejected_by_length_guard(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context", return_value="OK"):
                result = route("x" * 12000, uid="100")
        self.assertEqual(result, "OK")


if __name__ == "__main__":
    unittest.main()
