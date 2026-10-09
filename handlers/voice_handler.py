import io
import os
import requests

from core.ask_router import route
from core.conversation_memory import record_turn
from core.voice_output import synthesize_hebrew_voice

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



def _voice_reply_allowed(uid, message):
    if str(os.getenv("SLH_VOICE_REPLY_ENABLED", "1")).strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    if not uid or str(getattr(getattr(message, "chat", None), "type", "")).lower() != "private":
        return False
    try:
        from core.authority import get_role
        return get_role(uid) in {"OWNER", "ADMIN", "DEVELOPER"}
    except Exception:
        return False


def _send_spoken_reply(bot, message, uid, text):
    # Always preserve the normal text reply. TTS is an optional second channel.
    if not _voice_reply_allowed(uid, message):
        return
    audio, error = synthesize_hebrew_voice(text)
    if error or not audio:
        print("[VOICE] spoken reply unavailable:", error or "TTS_EMPTY_AUDIO")
        return
    try:
        voice_file = io.BytesIO(audio)
        voice_file.name = "slh-reply.ogg"
        bot.send_voice(
            message.chat.id,
            voice_file,
            reply_to_message_id=getattr(message, "message_id", None),
        )
    except Exception as exc:
        print("[VOICE] Telegram voice delivery failed:", type(exc).__name__)

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

            # Handle explicitly recognized, read-only owner operations before
            # general chat. Unknown speech remains conversational; financial
            # mutations and broadcasts are rejected by the operator router.
            from handlers.broadcast_handler import route_exchange_broadcast_voice
            from core.voice_operator_router import route_voice_operator_request

            broadcast_answer = route_exchange_broadcast_voice(bot, message, transcript)
            if broadcast_answer is not None:
                answer = broadcast_answer
            else:
                operator_answer = route_voice_operator_request(transcript, uid)
                answer = operator_answer if operator_answer is not None else route(transcript, uid)
            final_answer = _safe_answer(answer)

            bot.reply_to(message, final_answer, parse_mode=None)

            if (
                final_answer
                and not final_answer.startswith("🧠 ה־AI אינו זמין כרגע")
                and not final_answer.startswith("מנוע ה-AI לא זמין כרגע")
            ):
                record_turn(uid, transcript, final_answer, intent="voice")

            _send_spoken_reply(bot, message, uid, final_answer)

        except Exception as exc:
            print("[VOICE] handler error:", type(exc).__name__)
            bot.reply_to(message, "🎙️ אירעה תקלה בעיבוד ההודעה הקולית. נסה שוב.")


print("VOICE STT MODULE LOADED FROM:", __file__)
