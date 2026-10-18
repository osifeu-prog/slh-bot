import unittest

from handlers.owner_control_center_handler import _keyboard, callback_data, parse_callback


class StateCalibrationButtonTests(unittest.TestCase):
    def test_state_calibration_callback_is_recognized_and_expires(self):
        payload = callback_data("state_calibration", issued_at=1000)
        self.assertEqual(parse_callback(payload, now=1001), "state_calibration")
        self.assertIsNone(parse_callback(payload, now=1000 + 30 * 60 + 1))

    def test_control_center_keyboard_exposes_calibration_button(self):
        markup = _keyboard()
        buttons = [button for row in markup.keyboard for button in row]
        matching = [button for button in buttons if "3 מקורות" in str(button.text)]
        self.assertEqual(len(matching), 1)
        self.assertIn("state_calibration", str(matching[0].callback_data))
        self.assertIn("כיול", str(matching[0].text))


if __name__ == "__main__":
    unittest.main()
