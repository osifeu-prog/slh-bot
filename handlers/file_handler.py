"""Private, bounded document upload handling for the owner.

Do not write sender IDs or original filenames to a project-root journal.
Sensitive documents stay in the private runtime upload directory and use
server-generated filenames.
"""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

from core.authority import is_owner

UPLOAD_DIR = Path("state/uploads")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_SUFFIXES = {
    ".csv", ".doc", ".docx", ".gz", ".html", ".jpeg", ".jpg",
    ".json", ".md", ".pdf", ".png", ".tgz", ".txt", ".xls",
    ".xlsx", ".xml", ".yaml", ".yml", ".zip",
}


def _safe_suffix(original_name: str | None) -> str:
    suffix = Path(str(original_name or "")).suffix.lower()
    return suffix if suffix in _ALLOWED_SUFFIXES else ".bin"


def _store_upload(data: bytes, original_name: str | None) -> str:
    """Store bytes using a generated name and owner-only filesystem modes."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("UPLOAD_DATA_INVALID")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("UPLOAD_TOO_LARGE")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(UPLOAD_DIR, 0o700)
    suffix = _safe_suffix(original_name)

    for _ in range(5):
        name = f"upload_{int(time.time())}_{secrets.token_hex(8)}{suffix}"
        path = UPLOAD_DIR / name
        try:
            fd = os.open(
                str(path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            continue

        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            # Fail closed if private permissions cannot be enforced.
            os.chmod(path, 0o600)
            return name
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    raise RuntimeError("UPLOAD_NAME_COLLISION")


def register(bot):
    @bot.message_handler(content_types=["document"])
    def handle_document(message):
        chat = getattr(message, "chat", None)
        user = getattr(message, "from_user", None)
        uid = getattr(user, "id", None)

        # This runtime stores files in one shared server directory. Until
        # per-user storage and access controls exist, accept private uploads
        # from the owner only.
        if not is_owner(uid) or getattr(chat, "type", None) != "private":
            bot.reply_to(
                message,
                "⛔️ העלאת קבצים למרחב השרת זמינה כרגע לבעלים בלבד, בצ׳אט פרטי.",
            )
            return

        document = getattr(message, "document", None)
        if document is None:
            bot.reply_to(message, "❌ לא נמצא מסמך להעלאה.")
            return

        try:
            declared_size = int(getattr(document, "file_size", 0) or 0)
        except (TypeError, ValueError):
            declared_size = 0
        if declared_size < 0 or declared_size > MAX_UPLOAD_BYTES:
            bot.reply_to(message, "❌ גודל הקובץ חורג ממגבלת 10MB.")
            return

        try:
            file_info = bot.get_file(document.file_id)
            downloaded = bot.download_file(file_info.file_path)
            if len(downloaded) > MAX_UPLOAD_BYTES:
                bot.reply_to(message, "❌ גודל הקובץ חורג ממגבלת 10MB.")
                return

            stored_name = _store_upload(
                downloaded,
                getattr(document, "file_name", None),
            )
            bot.reply_to(
                message,
                "✅ הקובץ נשמר במרחב הפרטי של הבעלים.\n"
                f"מזהה מקומי: {stored_name}",
            )
        except Exception as exc:
            # Do not echo arbitrary exception text, source names, or paths.
            bot.reply_to(
                message,
                f"❌ שמירת הקובץ נכשלה ({type(exc).__name__}).",
            )
