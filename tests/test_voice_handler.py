import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

from handlers.voice_handler import register, transcribe_voice


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


    def test_privileged_private_voice_request_gets_spoken_reply(self):
        registered = {}

        def handler_decorator(**kwargs):
            def wrap(fn):
                registered["callback"] = fn
                return fn
            return wrap

        bot = Mock()
        bot.message_handler.side_effect = handler_decorator
        bot.get_file.return_value = SimpleNamespace(file_path="telegram/voice.ogg")
        bot.download_file.return_value = b"ogg-bytes"
        message = SimpleNamespace(
            message_id=123,
            from_user=SimpleNamespace(id=8789977826),
            chat=SimpleNamespace(id=8789977826, type="private"),
            voice=SimpleNamespace(file_id="voice-file", file_unique_id="voice-unique"),
        )

        with patch(
            "handlers.voice_handler.transcribe_voice",
            return_value=("בדוק את הבורסה", None),
        ), patch(
            "core.voice_operator_router.route_voice_operator_request",
            return_value="שער הבורסה פתוח וכל הבדיקות עברו.",
        ), patch(
            "handlers.voice_handler.route"
        ) as conversational_route, patch(
            "handlers.voice_handler.synthesize_hebrew_voice",
            return_value=(b"ogg-opus-bytes", None),
        ) as synthesize, patch(
            "core.authority.get_role",
            return_value="OWNER",
        ):
            register(bot)
            registered["callback"](message)

        conversational_route.assert_not_called()
        synthesize.assert_called_once_with("שער הבורסה פתוח וכל הבדיקות עברו.")
        bot.send_voice.assert_called_once()
        args, kwargs = bot.send_voice.call_args
        self.assertEqual(args[0], 8789977826)
        self.assertEqual(args[1].read(), b"ogg-opus-bytes")
        self.assertEqual(kwargs["reply_to_message_id"], 123)
        bot.reply_to.assert_called_once_with(
            message,
            "שער הבורסה פתוח וכל הבדיקות עברו.",
            parse_mode=None,
        )

    def test_regular_or_group_chat_never_sends_tts(self):
        registered = {}

        def handler_decorator(**kwargs):
            def wrap(fn):
                registered["callback"] = fn
                return fn
            return wrap

        bot = Mock()
        bot.message_handler.side_effect = handler_decorator
        bot.get_file.return_value = SimpleNamespace(file_path="telegram/voice.ogg")
        bot.download_file.return_value = b"ogg-bytes"
        message = SimpleNamespace(
            message_id=456,
            from_user=SimpleNamespace(id=12345),
            chat=SimpleNamespace(id=-100987654321, type="group"),
            voice=SimpleNamespace(file_id="voice-file", file_unique_id="voice-unique"),
        )

        with patch(
            "handlers.voice_handler.transcribe_voice",
            return_value=("בדוק את הבורסה", None),
        ), patch(
            "core.voice_operator_router.route_voice_operator_request",
            return_value="אין הרשאה.",
        ), patch(
            "handlers.voice_handler.route"
        ) as conversational_route, patch(
            "handlers.voice_handler.synthesize_hebrew_voice",
            return_value=(b"ogg-opus-bytes", None),
        ) as synthesize, patch(
            "core.authority.get_role",
            return_value="USER",
        ):
            register(bot)
            registered["callback"](message)

        synthesize.assert_not_called()
        bot.send_voice.assert_not_called()
        bot.reply_to.assert_called_once()

    def test_voice_handler_routes_operator_check_before_general_ai(self):
        registered = {}

        def handler_decorator(**kwargs):
            def wrap(fn):
                registered["callback"] = fn
                return fn
            return wrap

        bot = Mock()
        bot.message_handler.side_effect = handler_decorator
        bot.get_file.return_value = SimpleNamespace(file_path="telegram/voice.ogg")
        bot.download_file.return_value = b"ogg-bytes"
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=8789977826),
            chat=SimpleNamespace(id=8789977826),
            voice=SimpleNamespace(file_id="voice-file", file_unique_id="voice-unique"),
        )

        with patch(
            "handlers.voice_handler.transcribe_voice",
            return_value=("בדוק את הבורסה", None),
        ), patch(
            "core.voice_operator_router.route_voice_operator_request",
            return_value="🔎 Internal Exchange: PASS (READ ONLY)",
        ) as operator_route, patch(
            "handlers.voice_handler.route"
        ) as conversational_route, patch(
            "handlers.voice_handler.record_turn"
        ):
            register(bot)
            registered["callback"](message)

        operator_route.assert_called_once_with("בדוק את הבורסה", "8789977826")
        conversational_route.assert_not_called()
        bot.reply_to.assert_called_once_with(
            message,
            "🔎 Internal Exchange: PASS (READ ONLY)",
            parse_mode=None,
        )


if __name__ == "__main__":
    unittest.main()
