import unittest

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
                        self.assertLessEqual(len(button.callback_data.encode("utf-8")), 64)
                        self.assertTrue(button.callback_data.startswith("slh_pitch:"))

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


    def test_pitch_handler_registers_only_for_primary_bot_context(self):
        secondary_bot = FakeBot()
        register(secondary_bot, {"bot_name": "secondary_bot"})
        self.assertEqual(secondary_bot.message_handlers, [])
        self.assertEqual(secondary_bot.callback_handlers, [])

        main_bot = FakeBot()
        register(main_bot, {"bot_name": "Me_ad_main"})
        self.assertEqual(len(main_bot.message_handlers), 1)
        self.assertEqual(len(main_bot.callback_handlers), 1)
        self.assertEqual(main_bot.message_handlers[0][0]["commands"], ["pitch"])


if __name__ == "__main__":
    unittest.main()
