import unittest
from unittest.mock import patch

from core.ask_router import AI_MAX_INPUT_CHARS, _chunk_ai_input, _normalize_ai_input, route


class AiInputGuardTests(unittest.TestCase):
    def test_long_input_is_chunked_before_llm(self):
        long_input = "שורה ראשונה. " + ("x" * (AI_MAX_INPUT_CHARS + 2000))
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch(
                "core.ask_router.query_llm_with_context",
                side_effect=lambda q, uid=None: f"OK:{len(q)}",
            ) as llm:
                result = route(long_input, uid="100")
        self.assertIn("OK:", result)
        self.assertGreater(llm.call_count, 1)
        self.assertTrue(
            all(len(call.args[0]) <= AI_MAX_INPUT_CHARS + 120 for call in llm.call_args_list)
        )

    def test_normalization_preserves_lines_and_collapses_transport_whitespace(self):
        self.assertEqual(_normalize_ai_input("  a   b\r\n c\t d  "), "a b\nc d")

    def test_chunking_prefers_line_boundaries(self):
        text = ("a" * 900) + "\n" + ("b" * 900)
        chunks = _chunk_ai_input(text, max_chars=1000, max_chunks=4)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].endswith("a"))
        self.assertTrue(chunks[1].startswith("b"))

    def test_boundary_input_is_not_rejected_by_length_guard(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context", return_value="OK"):
                result = route("x" * 1500, uid="100")
        self.assertEqual(result, "OK")


if __name__ == "__main__":
    unittest.main()
