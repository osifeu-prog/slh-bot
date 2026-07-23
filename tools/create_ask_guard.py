from pathlib import Path

p = Path("core/ask_guard.py")

content = r'''
import time
import hashlib

_last_requests = {}

COOLDOWN_SECONDS = 8


def fingerprint(text):
    return hashlib.sha256(
        text.strip().lower().encode("utf-8")
    ).hexdigest()


def allow_request(text):
    key = fingerprint(text)
    now = time.time()

    if key in _last_requests:
        if now - _last_requests[key] < COOLDOWN_SECONDS:
            return False

    _last_requests[key] = now
    return True


def guarded_message():
    return "⏳ הבקשה כבר בטיפול. נסה שוב בעוד כמה שניות."
'''

p.write_text(content, encoding="utf-8")

print("ASK Guard created")
