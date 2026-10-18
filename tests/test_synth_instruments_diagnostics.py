import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from handlers import synth_engine
from handlers import synth_handler


ROOT = Path(__file__).resolve().parents[1]


class SynthInstrumentEngineTests(unittest.TestCase):
    def test_all_instrument_presets_render_finite_samples(self):
        for instrument in synth_engine.INSTRUMENTS:
            with self.subTest(instrument=instrument):
                settings = synth_engine.normalize_settings(instrument)
                samples = synth_engine.tone(["A4"], instrument, 0.2, settings)
                self.assertEqual(len(samples), int(synth_engine.SR * 0.2))
                self.assertTrue(all(math.isfinite(v) for v in samples))
                self.assertGreater(max(abs(v) for v in samples), 0.0)

    def test_frequency_references_are_equal_temperament(self):
        self.assertTrue(math.isclose(synth_engine.freq("A4"), 440.0, rel_tol=1e-10))
        self.assertTrue(math.isclose(synth_engine.freq("C4"), 261.6255653006, rel_tol=1e-9))
        self.assertTrue(math.isclose(synth_engine.freq("A3"), 220.0, rel_tol=1e-10))

    def test_settings_are_bounded_and_reject_non_finite_values(self):
        self.assertEqual(synth_engine.normalize_settings("moog", {"cutoff": 1250})["cutoff"], 1250)
        for value in (199, 12001, float("nan"), float("inf")):
            with self.subTest(cutoff=value):
                with self.assertRaises(ValueError):
                    synth_engine.normalize_settings("moog", {"cutoff": value})
        with self.assertRaises(ValueError):
            synth_engine.normalize_settings("unknown", None)

    def test_tone_rejects_invalid_note_in_every_preset(self):
        for instrument in synth_engine.INSTRUMENTS:
            with self.subTest(instrument=instrument):
                with self.assertRaises(ValueError):
                    synth_engine.tone(["H4"], instrument, 0.2)

    def test_legacy_wave_commands_remain_supported(self):
        for waveform in synth_engine.WAVES:
            with self.subTest(waveform=waveform):
                self.assertEqual(
                    len(synth_engine.tone(["C4"], waveform, 0.1)),
                    int(synth_engine.SR * 0.1),
                )


class SynthCommandSettingsTests(unittest.TestCase):
    def test_handler_parses_instrument_and_adsr_filter_suffix(self):
        class FakeBot:
            def __init__(self):
                self.registered = []
                self.voice_bytes = None
                self.replies = []

            def message_handler(self, **kwargs):
                def decorate(function):
                    self.registered.append((kwargs, function))
                    return function
                return decorate

            def reply_to(self, message, text, **kwargs):
                self.replies.append(text)

            def send_voice(self, chat_id, audio, **kwargs):
                self.voice_bytes = audio.read()

        class Obj:
            pass

        bot = FakeBot()
        synth_handler.register(bot)
        command = next(fn for opts, fn in bot.registered if opts.get("commands") == ["synth"])
        message = Obj()
        message.text = "/synth moog 0.4 A3 C4 E4 ;slh=0.02,0.18,0.72,0.2,1800,5"
        message.chat = Obj()
        message.chat.id = 123
        message.chat.type = "private"
        message.message_id = 77

        captured = {}
        def fake_main(score, waveform, duration, output_path, settings=None):
            captured.update(score=score, waveform=waveform, duration=duration, settings=settings)
            Path(output_path).write_bytes(b"fake-ogg")

        with patch.object(synth_handler.se, "main", side_effect=fake_main):
            command(message)

        self.assertEqual(captured["waveform"], "moog")
        self.assertEqual(captured["score"], "A3 C4 E4")
        self.assertEqual(captured["duration"], 0.4)
        self.assertEqual(captured["settings"]["cutoff"], 1800.0)
        self.assertEqual(captured["settings"]["resonance"], 5.0)
        self.assertEqual(bot.voice_bytes, b"fake-ogg")
        self.assertFalse(bot.replies)

    def test_handler_rejects_unsafe_settings(self):
        class FakeBot:
            def __init__(self):
                self.registered = []
                self.replies = []
            def message_handler(self, **kwargs):
                def decorate(self, fn):
                    self.registered.append((kwargs, fn))
                    return fn
                return lambda fn: decorate(self, fn)
            def reply_to(self, message, text, **kwargs):
                self.replies.append(text)
        class Obj:
            pass
        bot = FakeBot()
        synth_handler.register(bot)
        command = next(fn for opts, fn in bot.registered if opts.get("commands") == ["synth"])
        message = Obj()
        message.text = "/synth piano 0.4 A4 ;slh=0.02,0.1,0.7,0.15,25000,1"
        message.chat = Obj()
        message.chat.type = "group"
        message.chat.id = 123
        message.message_id = 77
        command(message)
        self.assertTrue(bot.replies)
        self.assertIn("שימוש", bot.replies[0])


class SynthUiDiagnosticsContractTests(unittest.TestCase):
    def test_ui_exposes_keyboard_presets_adsr_analysis_and_tuner(self):
        html = (ROOT / "synth_ui.html").read_text(encoding="utf-8")
        for marker in (
            'id="pianoKeyboard"', 'value="piano"', 'value="moog"',
            'id="attack"', 'id="decay"', 'id="sustain"', 'id="release"',
            'id="cutoff"', 'id="resonance"', 'id="scopeCanvas"',
            'id="spectrumCanvas"', 'id="testReference"', 'id="tunerProfile"',
            'id="startTuner"', 'id="stopTuner"', 'id="measuredHz"',
            ';slh=', 'getUserMedia', 'detectPitch', 'A4 = 440 Hz'
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

    def test_ui_posts_only_bounded_instrument_command_shape(self):
        handler = (ROOT / "handlers" / "synth_handler.py").read_text(encoding="utf-8")
        bridge = (ROOT / "handlers" / "webapp_data_handler.py").read_text(encoding="utf-8")
        self.assertIn("INSTRUMENTS = se.INSTRUMENTS", handler)
        self.assertIn('raw_score.partition(" ;slh=")', handler)
        self.assertIn("se.normalize_settings(waveform, settings)", handler)
        self.assertIn('len(cmd) <= 1200', bridge)
        self.assertIn('action == "synth"', bridge)


if __name__ == "__main__":
    unittest.main()
