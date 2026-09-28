import unittest
from unittest.mock import patch, Mock

from handlers.voice_handler import transcribe_voice


class TestVoiceSTT(unittest.TestCase):
    def test_transcribe_voice_success(self):
        fake = Mock()
        fake.status_code = 200
        fake.json.return_value = {"text": "שלום רובוטוש"}

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=False):
            with patch("handlers.voice_handler.requests.post", return_value=fake) as post:
                text, error = transcribe_voice(b"ogg-bytes", "voice.ogg")

        self.assertEqual(text, "שלום רובוטוש")
        self.assertIsNone(error)
        post.assert_called_once()
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["data"]["model"], "whisper-large-v3-turbo")
        self.assertEqual(kwargs["data"]["language"], "he")

    def test_transcribe_voice_missing_key(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": ""}, clear=False):
            text, error = transcribe_voice(b"ogg-bytes")

        self.assertIsNone(text)
        self.assertEqual(error, "GROQ_API_KEY_MISSING")


if __name__ == "__main__":
    unittest.main()
