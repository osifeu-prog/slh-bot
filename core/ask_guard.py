import time
import hashlib

_last_requests = {}

COOLDOWN_SECONDS = 8


def fingerprint(text, uid):
    return hashlib.sha256(
        (text.strip().lower() + ":" + str(uid)).encode("utf-8")
    ).hexdigest()


def allow_request(text, uid):
    key = fingerprint(text, uid)
    now = time.time()

    if key in _last_requests:
        if now - _last_requests[key] < COOLDOWN_SECONDS:
            return False

    _last_requests[key] = now
    return True


def guarded_message():
    return "⏳ הבקשה כבר בטיפול. נסה שוב בעוד כמה שניות."


def guard(text, uid=None):
    return allow_request(text, uid)
