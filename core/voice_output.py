"""Hebrew TTS for private, privileged Telegram voice replies.

The caller must keep a text response as the reliable fallback. Provider errors
are represented by stable codes; response bodies and secrets are never logged.
"""
import base64
import os
import re
import subprocess

import requests


GEMINI_TTS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_TTS_MODEL = "gemini-3.8-flash-lite-tts"
DEFAULT_TTS_TIMEOUT = 30
MAX_SPEECH_TEXT_CHARS = 680


def _api_key():
    return (os.getenv("GEMINI_API_KEY") or "").strip().strip('"\'')


def _speech_text(value):
    text = str(value or "").replace("\x00", " ").strip()
    # Emojis and Markdown are not useful to the speech model; keep Hebrew,
    # Latin, numbers and common punctuation.
    text = re.sub(r"[^\w\s.,:;!?()%/₪\-]", " ", text, flags=re.UNICODE)
    text = " ".join(text.split())
    if not text:
        return ""

    if len(text) > MAX_SPEECH_TEXT_CHARS:
        limit = MAX_SPEECH_TEXT_CHARS - 38
        clipped = text[:limit].rsplit(" ", 1)[0].strip()
        last_sentence = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
        if last_sentence >= int(limit * 0.55):
            clipped = clipped[:last_sentence + 1]
        text = (clipped or text[:limit].strip()) + " פירוט מלא מופיע בהודעה הכתובה."
    return text[:MAX_SPEECH_TEXT_CHARS]


def _wav_to_ogg_opus(wav_bytes):
    """Transcode Gemini's WAV output to Telegram-compatible OGG Opus."""
    if not wav_bytes:
        raise ValueError("TTS_EMPTY_AUDIO")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-nostdin",
        "-f", "wav",
        "-i", "pipe:0",
        "-ac", "1",
        "-ar", "24000",
        "-c:a", "libopus",
        "-b:a", "32k",
        "-application", "voip",
        "-f", "ogg",
        "pipe:1",
    ]
    completed = subprocess.run(
        command,
        input=wav_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=25,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        raise RuntimeError("TTS_CONVERSION_FAILED")
    return completed.stdout


def _extract_audio_data(result):
    """Return (base64 audio, MIME type) from SDK-style or raw REST responses."""
    if not isinstance(result, dict):
        return None, None

    output_audio = result.get("output_audio")
    if isinstance(output_audio, dict) and output_audio.get("data"):
        return (
            output_audio["data"],
            str(output_audio.get("mime_type") or "audio/wav").lower(),
        )

    # Raw REST Interactions responses store audio in steps[].content[].
    steps = result.get("steps")
    if isinstance(steps, list):
        for step in reversed(steps):
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            blocks = step.get("content")
            if not isinstance(blocks, list):
                continue
            for block in reversed(blocks):
                if isinstance(block, dict) and block.get("type") == "audio" and block.get("data"):
                    return (
                        block["data"],
                        str(block.get("mime_type") or "audio/wav").lower(),
                    )
    return None, None


def synthesize_hebrew_voice(text):
    """Return (ogg_opus_bytes, None) or (None, stable_error_code)."""
    api_key = _api_key()
    if not api_key:
        return None, "TTS_API_KEY_MISSING"

    spoken_text = _speech_text(text)
    if not spoken_text:
        return None, "TTS_TEXT_EMPTY"

    model = (os.getenv("SLH_VOICE_TTS_MODEL") or DEFAULT_TTS_MODEL).strip()
    try:
        timeout = max(5, min(45, int(os.getenv("SLH_VOICE_TTS_TIMEOUT_SECONDS", str(DEFAULT_TTS_TIMEOUT)))))
    except ValueError:
        timeout = DEFAULT_TTS_TIMEOUT

    payload = {
        "model": model,
        "input": spoken_text,
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {"speech_config": [{"voice": "Kore"}]},
    }
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
        "Api-Revision": "2026-05-20",
    }
    try:
        response = requests.post(
            GEMINI_TTS_URL,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout:
        return None, "TTS_REQUEST_TIMEOUT"
    except requests.RequestException as exc:
        return None, f"TTS_REQUEST_ERROR:{type(exc).__name__}"

    if response.status_code >= 400:
        return None, f"TTS_HTTP_{response.status_code}"

    try:
        result = response.json()
        encoded_audio, mime_type = _extract_audio_data(result)
        if not encoded_audio:
            return None, "TTS_AUDIO_MISSING"
        if mime_type not in {"audio/wav", "audio/x-wav"}:
            return None, "TTS_UNSUPPORTED_AUDIO_FORMAT"
        wav_bytes = base64.b64decode(encoded_audio, validate=True)
    except (ValueError, TypeError, AttributeError):
        return None, "TTS_INVALID_RESPONSE"

    try:
        return _wav_to_ogg_opus(wav_bytes), None
    except FileNotFoundError:
        return None, "TTS_FFMPEG_MISSING"
    except subprocess.TimeoutExpired:
        return None, "TTS_CONVERSION_TIMEOUT"
    except Exception as exc:
        # Never include provider body, generated text, key or local paths.
        return None, f"TTS_CONVERSION_ERROR:{type(exc).__name__}"
