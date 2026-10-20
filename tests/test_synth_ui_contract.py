import math
from pathlib import Path
import unittest

from handlers import synth_engine


ROOT = Path(__file__).resolve().parents[1]


class SynthUiContractTests(unittest.TestCase):
    def test_standalone_ui_has_bounded_controls_and_send_fallback(self):
        html = (ROOT / "synth_ui.html").read_text(encoding="utf-8")
        self.assertIn('id="wave"', html)
        self.assertIn('id="duration"', html)
        self.assertIn('id="addStep"', html)
        self.assertIn("steps.length>=16", html)
        self.assertIn("tg.sendData(JSON.stringify({cmd:cmd}))", html)
        self.assertIn("copyCommand()", html)
        self.assertIn("/synth ", html)

    def test_server_route_and_mini_app_entry_are_present(self):
        source = (ROOT / "webapp.py").read_text(encoding="utf-8")
        self.assertIn('@app.route("/synth-ui")', source)
        self.assertIn('BASE_DIR / "synth_ui.html"', source)
        self.assertIn("slh-synth-miniapp-entry", source)
        self.assertIn("/synth-ui?source=miniapp", source)
        self.assertIn('"Cache-Control"] = "no-store', source)

    def test_market_lab_score_prefill_is_bounded_and_keeps_user_in_control(self):
        html = (ROOT / "synth_ui.html").read_text(encoding="utf-8")
        self.assertIn("function parseMarketScore(raw)", html)
        self.assertIn("raw.length>720", html)
        self.assertIn("rawSteps.length>16", html)
        self.assertIn("notes.length>8", html)
        self.assertIn("noteToMidi(note)===null", html)
        self.assertIn("source === 'market-lab'", html)
        self.assertIn("market_demo", html)
        self.assertIn("העתק לבוט", html)
        self.assertIn("window.location.assign('/market-lab')", html)

    def test_bot_offers_private_web_app_button(self):
        source = (ROOT / "handlers" / "synth_handler.py").read_text(encoding="utf-8")
        self.assertIn('commands=["synth_ui", "synthui"]', source)
        self.assertIn("types.ReplyKeyboardMarkup", source)
        self.assertIn("types.WebAppInfo", source)
        self.assertIn('"/synth-ui"', source)

    def test_web_app_bridge_only_forwards_bounded_private_synth_commands(self):
        source = (ROOT / "handlers" / "webapp_data_handler.py").read_text(encoding="utf-8")
        self.assertIn('action == "synth"', source)
        self.assertIn('cmd.startswith("/synth ")', source)
        self.assertIn("len(cmd) <= 1200", source)
        self.assertIn("len(parts) <= 132", source)
        self.assertIn('message.chat, "type"', source)
        self.assertIn("bot.process_new_messages([message])", source)


class SynthEngineTests(unittest.TestCase):
    def test_reference_frequencies(self):
        self.assertTrue(math.isclose(synth_engine.freq("A4"), 440.0, rel_tol=1e-10))
        self.assertTrue(math.isclose(synth_engine.freq("C4"), 261.6255653006, rel_tol=1e-9))

    def test_tone_length_matches_sample_rate_and_duration(self):
        expected = int(synth_engine.SR * 0.1)
        samples = synth_engine.tone(["C4", "E4", "G4"], "sine", 0.1)
        self.assertEqual(len(samples), expected)
        self.assertTrue(all(math.isfinite(value) for value in samples))

    def test_invalid_notes_and_waveforms_fail_closed(self):
        with self.assertRaises(ValueError):
            synth_engine.freq("H4")
        with self.assertRaises(ValueError):
            synth_engine.osc("triangle", 0.25)


if __name__ == "__main__":
    unittest.main()
