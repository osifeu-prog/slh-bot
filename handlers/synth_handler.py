import os
import re
import tempfile

from handlers import synth_engine as se

WAVES = ("sine", "saw", "square", "tri")
NOTE = re.compile(r"[A-G][#b]?[0-8]$")
USAGE = (
    "שימוש: /synth <sine|saw|square|tri> <משך 0.1-1.5> <תווים>\n"
    "רווח = אקורד, פסיק = צעד הבא\n"
    "דוגמה: /synth saw 0.6 C4 E4 G4,F4 A4 C5"
)


def register(bot):
    @bot.message_handler(commands=["synth"])
    def synth(message):
        parts = (message.text or "").split(None, 3)
        try:
            if len(parts) != 4:
                raise ValueError
            waveform = parts[1].lower()
            duration = float(parts[2])
            score = parts[3]
            steps = score.split(",")
            valid = (
                waveform in WAVES
                and 0.1 <= duration <= 1.5
                and 1 <= len(steps) <= 16
                and all(step.split() and len(step.split()) <= 8 for step in steps)
                and all(NOTE.fullmatch(note) for step in steps for note in step.split())
            )
            if not valid:
                raise ValueError
        except (ValueError, IndexError):
            bot.reply_to(message, USAGE)
            return

        output_path = None
        try:
            fd, output_path = tempfile.mkstemp(prefix="slh-synth-", suffix=".ogg")
            os.close(fd)
            se.main(score, waveform, duration, output_path)
            with open(output_path, "rb") as audio:
                audio.name = "slh-synth.ogg"
                bot.send_voice(message.chat.id, audio, reply_to_message_id=getattr(message, "message_id", None))
        except Exception as exc:
            bot.reply_to(message, "לא הצלחתי ליצור את קובץ השמע כרגע.")
            print("[SYNTH] generation/delivery failed:", type(exc).__name__)
        finally:
            if output_path:
                try:
                    os.remove(output_path)
                except FileNotFoundError:
                    pass
