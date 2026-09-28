import os
import requests

from core.ask_router import route
from core.conversation_memory import record_turn

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_STT_MODEL = "whisper-large-v3-turbo"
DEFAULT_STT_TIMEOUT = 60
MAX_TRANSCRIPT_CHARS = 1500


def _groq_key():
    return (os.getenv("GROQ_API_KEY") or "").strip().strip('"\'')


def transcribe_voice(audio_bytes, filename="voice.ogg"):
    key = _groq_key()
    if not key:
        return None, "GROQ_API_KEY_MISSING"

    model = (os.getenv("GROQ_STT_MODEL") or "").strip() or DEFAULT_STT_MODEL
    try:
        timeout = max(10, int(os.getenv("GROQ_STT_TIMEOUT_SECONDS", str(DEFAULT_STT_TIMEOUT))))
    except ValueError:
        timeout = DEFAULT_STT_TIMEOUT

    files = {"file": (filename or "voice.ogg", audio_bytes, "audio/ogg")}
    data = {
        "model": model,
        "language": "he",
        "response_format": "json",
        "temperature": "0",
    }

    try:
        response = requests.post(
            GROQ_STT_URL,
            headers={"Authorization": f"Bearer {key}"},
            files=files,
            data=data,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return None, f"STT_REQUEST_ERROR:{type(exc).__name__}"

    if response.status_code >= 400:
        return None, f"STT_HTTP_{response.status_code}"

    try:
        payload = response.json()
    except ValueError:
        return None, "STT_INVALID_RESPONSE"

    text = str(payload.get("text") or "").strip()
    if not text:
        return None, "STT_EMPTY"

    return text, None


def _safe_answer(value, limit=3500):
    text = str(value if value is not None else "").replace("\x00", "").strip()
    if len(text) > limit:
        return text[:limit] + "\n...[truncated]"
    return text or "⚠️ לא התקבלה תשובה."


def register(bot):
    @bot.message_handler(content_types=["voice"])
    def handle_voice(message):
        uid = str(message.from_user.id) if message.from_user else None

        try:
            bot.send_chat_action(message.chat.id, "typing")
            file_info = bot.get_file(message.voice.file_id)
            audio = bot.download_file(file_info.file_path)

            transcript, error = transcribe_voice(
                audio,
                filename=f"voice_{getattr(message.voice, 'file_unique_id', 'telegram')}.ogg",
            )
            if error:
                bot.reply_to(message, "🎙️ לא הצלחתי לתמלל את ההודעה הקולית כרגע. נסה שוב בעוד רגע.")
                print("[VOICE] STT failed:", error)
                return

            if len(transcript) > MAX_TRANSCRIPT_CHARS:
                bot.reply_to(
                    message,
                    f"🎙️ התמלול ארוך מדי לעיבוד AI. קצר את ההודעה לעד {MAX_TRANSCRIPT_CHARS} תווים ונסה שוב.",
                )
                return

            answer = route(transcript, uid)
            final_answer = _safe_answer(answer)

            bot.reply_to(message, final_answer, parse_mode=None)

            if (
                final_answer
                and not final_answer.startswith("🧠 ה־AI אינו זמין כרגע")
                and not final_answer.startswith("מנוע ה-AI לא זמין כרגע")
            ):
                record_turn(uid, transcript, final_answer, intent="voice")

        except Exception as exc:
            print("[VOICE] handler error:", type(exc).__name__)
            bot.reply_to(message, "🎙️ אירעה תקלה בעיבוד ההודעה הקולית. נסה שוב.")


print("VOICE STT MODULE LOADED FROM:", __file__)
