import io
import os
import re
import tempfile

from telebot import types
from handlers import synth_engine as se

WAVES = se.WAVES
INSTRUMENTS = se.INSTRUMENTS
NOTE = re.compile(r"[A-G][#b]?[0-8]$")
USAGE = (
    "שימוש: /synth <sine|saw|square|tri|piano|moog|bass|organ|pluck> <משך 0.1-1.5> <תווים> [;slh=attack,decay,sustain,release,cutoff,resonance]\n"
    "רווח = אקורד, פסיק = צעד הבא\n"
    "דוגמה: /synth piano 0.6 C4 E4 G4,F4 A4 C5\n"
    "ADSR ופילטר אופציונליים נשלטים מהממשק; ערכיהם נבדקים בגבולות בטוחים."
)


def _synth_ui_url(source=None):
    base = (
        os.getenv("SLH_PUBLIC_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or "https://slh-cloud-bot-production.up.railway.app"
    ).strip().rstrip("/")
    url = base + "/synth-ui"
    return url + ("?source=" + source if source else "")


def _synth_inline_button():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "🎹 פתח ממשק סינתיסייזר",
        web_app=types.WebAppInfo(url=_synth_ui_url("inline")),
    ))
    return markup


def register(bot):
    @bot.message_handler(commands=["synth_ui", "synthui"])
    def synth_ui(message):
        chat_type = str(getattr(getattr(message, "chat", None), "type", "")).lower()
        if chat_type != "private":
            bot.reply_to(message, "פתח את הממשק בשיחה הפרטית עם הבוט.")
            return
        markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=True,
            row_width=1,
        )
        markup.add(types.KeyboardButton(
            "🎹 פתח ממשק סינתיסייזר",
            web_app=types.WebAppInfo(url=_synth_ui_url()),
        ))
        bot.send_message(
            message.chat.id,
            "🎹 בנה אקורדים, נגן תצוגה מקדימה ושלח את הרצף לבוט לקבלת קובץ שמע.",
            reply_markup=markup,
        )

    @bot.message_handler(commands=["synth"])
    def synth(message):
        parts = (message.text or "").split(None, 3)
        try:
            if len(parts) != 4:
                raise ValueError
            waveform = parts[1].lower()
            duration = float(parts[2])
            raw_score = parts[3]
            settings = None
            score, marker, raw_settings = raw_score.partition(" ;slh=")
            score = score.strip()
            if marker:
                values = raw_settings.split(",")
                if len(values) != len(se.SETTING_KEYS):
                    raise ValueError("INVALID_SYNTH_SETTINGS")
                settings = dict(zip(se.SETTING_KEYS, (float(v) for v in values)))
                settings = se.normalize_settings(waveform, settings)
            steps = score.split(",")
            valid = (
                waveform in INSTRUMENTS
                and 0.1 <= duration <= 1.5
                and 1 <= len(steps) <= 16
                and all(step.split() and len(step.split()) <= 8 for step in steps)
                and all(NOTE.fullmatch(note) for step in steps for note in step.split())
            )
            if not valid:
                raise ValueError("INVALID_SYNTH_COMMAND")
        except (ValueError, IndexError):
            markup = _synth_inline_button() if str(getattr(getattr(message, "chat", None), "type", "")).lower() == "private" else None
            bot.reply_to(message, USAGE, reply_markup=markup)
            return

        output_path = None
        try:
            fd, output_path = tempfile.mkstemp(prefix="slh-synth-", suffix=".ogg")
            os.close(fd)
            se.main(score, waveform, duration, output_path, settings=settings)
            with open(output_path, "rb") as source:
                audio = io.BytesIO(source.read())
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
