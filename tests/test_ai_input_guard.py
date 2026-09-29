import unittest
from unittest.mock import patch

from core.ask_router import AI_CHUNK_CHARS, normalize_and_chunk_ai_input, route


class AiInputGuardTests(unittest.TestCase):
    def test_normalizer_removes_nulls_and_normalizes_line_endings(self):
        self.assertEqual(
            normalize_and_chunk_ai_input(" a\r\nb\x00 "),
            ["a\nb"],
        )

    def test_long_input_is_chunked_instead_of_rejected(self):
        text = ("alpha " * 600).strip()
        chunks = normalize_and_chunk_ai_input(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(part) <= AI_CHUNK_CHARS for part in chunks))

    def test_single_chunk_reaches_llm(self):
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch("core.ask_router.query_llm_with_context", return_value="OK") as llm:
                result = route("x" * 1501, uid="100")
        self.assertEqual(result, "OK")
        self.assertEqual(llm.call_count, 1)

    def test_chunked_input_reaches_llm_and_synthesizes(self):
        text = ("alpha " * 600).strip()
        with patch("core.ask_router.guard", return_value=(True, "")):
            with patch(
                "core.ask_router.query_llm_with_context",
                side_effect=["PART 1", "PART 2", "SYNTHESIS"],
            ) as llm:
                result = route(text, uid="100")
        self.assertEqual(result, "SYNTHESIS")
        self.assertEqual(llm.call_count, 3)


if __name__ == "__main__":
    unittest.main()
