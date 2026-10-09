import base64
import os
import unittest
from unittest.mock import Mock, patch

from core.voice_output import synthesize_hebrew_voice


class TestHebrewVoiceOutput(unittest.TestCase):
    def test_missing_gemini_key_returns_text_fallback_signal(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            audio, error = synthesize_hebrew_voice("בדיקת מערכת תקינה")

        self.assertIsNone(audio)
        self.assertEqual(error, "TTS_API_KEY_MISSING")

    def test_hebrew_text_uses_gemini_tts_and_returns_telegram_opus_payload(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "output_audio": {"data": base64.b64encode(b"raw-pcm").decode("ascii")}
        }

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False), patch(
            "core.voice_output.requests.post", return_value=response
        ) as post, patch(
            "core.voice_output._pcm_to_ogg_opus", return_value=b"ogg-opus-bytes"
        ) as convert:
            audio, error = synthesize_hebrew_voice("שער הבורסה פתוח")

        self.assertEqual(audio, b"ogg-opus-bytes")
        self.assertIsNone(error)
        post.assert_called_once()
        args = post.call_args
        self.assertEqual(args.args[0], "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(args.kwargs["headers"]["x-goog-api-key"], "test-key")
        payload = args.kwargs["json"]
        self.assertEqual(payload["model"], "gemini-3.1-flash-tts-preview")
        self.assertEqual(payload["input"], "שער הבורסה פתוח")
        self.assertEqual(payload["response_format"], {"type": "audio"})
        self.assertEqual(payload["generation_config"]["speech_config"], [{"voice": "Kore"}])
        convert.assert_called_once_with(b"raw-pcm")

    def test_http_error_is_reported_without_leaking_provider_body(self):
        response = Mock()
        response.status_code = 429
        response.json.return_value = {"error": {"message": "private provider response"}}

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False), patch(
            "core.voice_output.requests.post", return_value=response
        ):
            audio, error = synthesize_hebrew_voice("בדיקת מערכת")

        self.assertIsNone(audio)
        self.assertEqual(error, "TTS_HTTP_429")
        self.assertNotIn("private provider response", error)

    def test_long_text_is_bounded_before_sending_to_tts_provider(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "output_audio": {"data": base64.b64encode(b"raw-pcm").decode("ascii")}
        }
        long_text = ("בדיקת מערכת. " * 200)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False), patch(
            "core.voice_output.requests.post", return_value=response
        ) as post, patch(
            "core.voice_output._pcm_to_ogg_opus", return_value=b"ogg-opus-bytes"
        ):
            audio, error = synthesize_hebrew_voice(long_text)

        self.assertEqual(audio, b"ogg-opus-bytes")
        self.assertIsNone(error)
        self.assertLessEqual(len(post.call_args.kwargs["json"]["input"]), 700)


    def test_tts_parses_audio_from_raw_interactions_rest_steps(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "steps": [
                {
                    "type": "model_output",
                    "content": [
                        {"type": "text", "text": "spoken response"},
                        {
                            "type": "audio",
                            "mime_type": "audio/wav",
                            "data": base64.b64encode(b"raw-rest-pcm").decode("ascii"),
                        },
                    ],
                }
            ]
        }

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False), patch(
            "core.voice_output.requests.post", return_value=response
        ), patch(
            "core.voice_output._pcm_to_ogg_opus", return_value=b"ogg-opus-bytes"
        ) as convert:
            audio, error = synthesize_hebrew_voice("תשובה קולית בעברית")

        self.assertEqual(audio, b"ogg-opus-bytes")
        self.assertIsNone(error)
        convert.assert_called_once_with(b"raw-rest-pcm")


if __name__ == "__main__":
    unittest.main()
