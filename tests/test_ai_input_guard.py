import unittest
from unittest.mock import patch

from core.ask_router import AI_INPUT_TOO_LONG_MESSAGE, route


class AiInputGuardTests(unittest.TestCase):
    def test_long_input_is_rejected_before_llm(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context") as llm:
                result = route("x" * 4001, uid="100")
        self.assertEqual(result, AI_INPUT_TOO_LONG_MESSAGE)
        llm.assert_not_called()

    def test_boundary_input_is_not_rejected_by_length_guard(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context", return_value="OK"):
                result = route("x" * 4000, uid="100")
        self.assertEqual(result, "OK")


if __name__ == "__main__":
    unittest.main()
