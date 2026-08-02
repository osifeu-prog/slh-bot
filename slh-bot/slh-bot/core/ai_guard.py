import time
import json
import os
from pathlib import Path


STATE_FILE = Path("state/ai_health.json")

MAX_FAILURES = 3
COOLDOWN = 120


def load_state():
    if not STATE_FILE.exists():
        return {
            "groq": {
                "failures": 0,
                "blocked_until": 0
            }
        }

    try:
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

    except Exception:
        return {
            "groq": {
                "failures": 0,
                "blocked_until": 0
            }
        }


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def provider_available(name="groq"):
    """
    Returns True only when:

    1. Required provider credentials exist.
    2. Circuit breaker is not active.
    """

    # Credential gate
    if name == "groq":
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            return False

    # Circuit breaker gate
    state = load_state()

    provider = state.setdefault(
        name,
        {
            "failures": 0,
            "blocked_until": 0
        }
    )

    return time.time() >= provider.get("blocked_until", 0)


def provider_success(name="groq"):
    state = load_state()

    provider = state.setdefault(
        name,
        {
            "failures": 0,
            "blocked_until": 0
        }
    )

    provider["failures"] = 0
    provider["blocked_until"] = 0

    save_state(state)


def provider_failure(name="groq"):
    state = load_state()

    provider = state.setdefault(
        name,
        {
            "failures": 0,
            "blocked_until": 0
        }
    )

    provider["failures"] = provider.get("failures", 0) + 1

    if provider["failures"] >= MAX_FAILURES:
        provider["blocked_until"] = time.time() + COOLDOWN

    save_state(state)


def status():
    return load_state()


def guard(text):
    return True


def guarded_message():
    return "⏳ הבקשה כבר בטיפול. נסה שוב בעוד כמה שניות."
