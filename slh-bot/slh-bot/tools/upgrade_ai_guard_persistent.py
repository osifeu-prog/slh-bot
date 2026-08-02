from pathlib import Path

p = Path("core/ai_guard.py")

content = r'''
import time
import json
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
    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def provider_available(name="groq"):
    state = load_state()

    provider = state.setdefault(
        name,
        {
            "failures": 0,
            "blocked_until": 0
        }
    )

    return time.time() >= provider["blocked_until"]


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

    provider["failures"] += 1

    if provider["failures"] >= MAX_FAILURES:
        provider["blocked_until"] = time.time() + COOLDOWN

    save_state(state)


def status():
    return load_state()


def guard(text):
    return True
'''

p.write_text(content, encoding="utf-8")

print("Persistent AI Guard installed")
