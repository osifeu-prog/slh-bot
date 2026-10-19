import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from handlers.pitch_handler import (
    PITCH_SLIDES,
    SIMULATION_DEMO,
    build_slide_keyboard,
    render_slide,
    render_simulation_demo,
    register,
)


class FakeBot:
    def __init__(self):
        self.message_handlers = []
        self.callback_handlers = []
        self.sent_messages = []
        self.callback_answers = []
        self.edited_messages = []

    def send_message(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.callback_answers.append((args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        self.edited_messages.append((args, kwargs))

    def message_handler(self, **kwargs):
        def decorate(fn):
            self.message_handlers.append((kwargs, fn))
            return fn
        return decorate

    def callback_query_handler(self, **kwargs):
        def decorate(fn):
            self.callback_handlers.append((kwargs, fn))
            return fn
        return decorate


class PitchHandlerTests(unittest.TestCase):
    def test_slides_are_complete_and_numbered(self):
        self.assertGreaterEqual(len(PITCH_SLIDES), 6)
        for index, slide in enumerate(PITCH_SLIDES):
            with self.subTest(index=index):
                self.assertTrue(slide["title"].strip())
                self.assertTrue(slide["body"].strip())
                self.assertIn(f"מסך {index + 1}/{len(PITCH_SLIDES)}", render_slide(index))

    def test_index_is_bounded(self):
        self.assertEqual(render_slide(-100), render_slide(0))
        self.assertEqual(render_slide(10_000), render_slide(len(PITCH_SLIDES) - 1))

    def test_simulation_is_clearly_marked_synthetic(self):
        demo = render_simulation_demo()
        self.assertEqual(demo, SIMULATION_DEMO)
        self.assertIn("נתונים סינתטיים בלבד", demo)
        self.assertIn("SIM-DEMO-001", demo)
        self.assertIn("לא נכתבה רשומה", demo)
        self.assertIn("אינה עסקה אמיתית", demo)

    def test_keyboard_callbacks_are_bounded(self):
        for index in range(len(PITCH_SLIDES)):
            keyboard = build_slide_keyboard(index)
            with self.subTest(index=index):
                self.assertTrue(keyboard.keyboard)
                for row in keyboard.keyboard:
                    for button in row:
                        if button.callback_data is not None:
                            self.assertLessEqual(len(button.callback_data.encode("utf-8")), 64)
                            self.assertTrue(button.callback_data.startswith("slh_pitch:"))
                        if button.url is not None:
                            self.assertTrue(button.url.startswith("https://"))

    def test_academy_callback_does_not_expose_course_progress_in_groups(self):
        bot = FakeBot()
        register(bot, {"bot_name": "Me_ad_main"})
        callback_handler = bot.callback_handlers[0][1]
        call = SimpleNamespace(
            id="callback-1",
            data="slh_pitch:academy",
            from_user=SimpleNamespace(id=12345),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=-100123, type="supergroup"),
                message_id=456,
            ),
        )

        callback_handler(call)

        self.assertEqual(len(bot.callback_answers), 1)
        self.assertIn("שיחה פרטית", bot.callback_answers[0][0][1])
        self.assertEqual(bot.sent_messages, [])
        self.assertEqual(bot.edited_messages, [])

    def test_tokenomics_slide_links_to_source_and_current_status(self):
        keyboard = build_slide_keyboard(2)
        urls = {
            button.text: button.url
            for row in keyboard.keyboard
            for button in row
            if button.url
        }
        self.assertEqual(
            urls.get("📄 Whitepaper v1.0"),
            "https://slh-nft.com/whitepaper.html",
        )
        self.assertEqual(
            urls.get("📣 דף IDO / Pre-launch"),
            "https://slh-nft.com/ido.html",
        )
        self.assertEqual(
            urls.get("🔎 סטטוס קנוני"),
            "https://slh-nft.com/status.html",
        )
        self.assertEqual(
            urls.get("🌐 אתר ציבורי"),
            "https://slh-nft.com/",
        )
        body = PITCH_SLIDES[2]["body"]
        self.assertIn("Whitepaper v1.0 (April 2026)", body)
        self.assertIn("המסומן Pre-launch", body)
        self.assertIn("אינה מציגה הקצאות", body)
        self.assertIn("לא הוכחה שהמסלול פתוח או סגור", body)
        self.assertNotIn("Whitepaper v2.0", body)
        self.assertNotIn("אין כרגע הצעת IDO/Presale ציבורית", body)

    def test_academy_button_is_available_on_academy_and_partnership_slides(self):
        for index in (1, len(PITCH_SLIDES) - 1):
            with self.subTest(index=index):
                callbacks = {
                    button.callback_data
                    for row in build_slide_keyboard(index).keyboard
                    for button in row
                    if button.callback_data
                }
                self.assertIn("slh_pitch:academy", callbacks)

    def test_simulation_button_only_on_controls_slide(self):
        controls = build_slide_keyboard(4)
        controls_callbacks = {
            button.callback_data
            for row in controls.keyboard
            for button in row
        }
        self.assertIn("slh_pitch:sim", controls_callbacks)

        first = build_slide_keyboard(0)
        first_callbacks = {
            button.callback_data
            for row in first.keyboard
            for button in row
        }
        self.assertNotIn("slh_pitch:sim", first_callbacks)


    def test_pitch_handler_requires_explicit_primary_bot_context(self):
        missing_context_bot = FakeBot()
        register(missing_context_bot)
        self.assertEqual(missing_context_bot.message_handlers, [])
        self.assertEqual(missing_context_bot.callback_handlers, [])

        secondary_bot = FakeBot()
        register(secondary_bot, {"bot_name": "secondary_bot"})
        self.assertEqual(secondary_bot.message_handlers, [])
        self.assertEqual(secondary_bot.callback_handlers, [])

        main_bot = FakeBot()
        register(main_bot, {"bot_name": "Me_ad_main"})
        self.assertEqual(len(main_bot.message_handlers), 1)
        self.assertEqual(len(main_bot.callback_handlers), 1)
        self.assertEqual(main_bot.message_handlers[0][0]["commands"], ["pitch"])


    def test_pitch_command_sends_first_slide_and_navigation(self):
        bot = FakeBot()
        register(bot, {"bot_name": "Me_ad_main"})
        command_handler = bot.message_handlers[0][1]
        message = SimpleNamespace(chat=SimpleNamespace(id=100, type="private"))

        command_handler(message)

        self.assertEqual(len(bot.sent_messages), 1)
        args, kwargs = bot.sent_messages[0]
        self.assertEqual(args[0], 100)
        self.assertIn("מסך 1/6", args[1])
        callbacks = {
            button.callback_data
            for row in kwargs["reply_markup"].keyboard
            for button in row
            if button.callback_data
        }
        self.assertIn("slh_pitch:slide:1", callbacks)

    def test_slide_navigation_edits_the_current_message(self):
        bot = FakeBot()
        register(bot, {"bot_name": "Me_ad_main"})
        callback_handler = bot.callback_handlers[0][1]
        call = SimpleNamespace(
            id="callback-slide",
            data="slh_pitch:slide:1",
            from_user=SimpleNamespace(id=123),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=100, type="private"),
                message_id=456,
            ),
        )

        callback_handler(call)

        self.assertEqual(len(bot.callback_answers), 1)
        self.assertEqual(len(bot.edited_messages), 1)
        args, kwargs = bot.edited_messages[0]
        self.assertIn("מסך 2/6", args[0])
        self.assertEqual(kwargs["chat_id"], 100)
        self.assertEqual(kwargs["message_id"], 456)

    def test_simulation_callback_displays_only_the_synthetic_demo(self):
        bot = FakeBot()
        register(bot, {"bot_name": "Me_ad_main"})
        callback_handler = bot.callback_handlers[0][1]
        call = SimpleNamespace(
            id="callback-sim",
            data="slh_pitch:sim",
            from_user=SimpleNamespace(id=123),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=100, type="private"),
                message_id=456,
            ),
        )

        callback_handler(call)

        self.assertEqual(len(bot.edited_messages), 1)
        args, kwargs = bot.edited_messages[0]
        self.assertIn("SIM-DEMO-001", args[0])
        self.assertIn("נתונים סינתטיים בלבד", args[0])
        self.assertIn("לא נכתבה רשומה", args[0])
        self.assertNotIn("ledger_entry", kwargs)

    def test_academy_callback_dispatches_only_in_private_chat(self):
        bot = FakeBot()
        register(bot, {"bot_name": "Me_ad_main"})
        callback_handler = bot.callback_handlers[0][1]
        calls = []
        academy_module = ModuleType("handlers.academy_menu_handler")
        academy_module._send_academy = lambda *args: calls.append(args)
        call = SimpleNamespace(
            id="callback-academy",
            data="slh_pitch:academy",
            from_user=SimpleNamespace(id=12345),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=100, type="private"),
                message_id=456,
            ),
        )

        with patch.dict("sys.modules", {"handlers.academy_menu_handler": academy_module}):
            callback_handler(call)

        self.assertEqual(calls, [(bot, 100, "12345")])
        self.assertEqual(bot.sent_messages, [])

    def test_invalid_slide_callback_is_rejected_without_editing(self):
        bot = FakeBot()
        register(bot, {"bot_name": "Me_ad_main"})
        callback_handler = bot.callback_handlers[0][1]
        call = SimpleNamespace(
            id="callback-invalid",
            data="slh_pitch:slide:999",
            from_user=SimpleNamespace(id=123),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=100, type="private"),
                message_id=456,
            ),
        )

        callback_handler(call)

        self.assertIn("מסך לא תקין", bot.callback_answers[0][0][1])
        self.assertEqual(bot.edited_messages, [])


if __name__ == "__main__":
    unittest.main()
