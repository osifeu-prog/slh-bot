from pathlib import Path

p = Path("core/ai_guard.py")

content = r'''
import time

_provider_state = {
    "groq": {
        "failures": 0,
        "blocked_until": 0
    }
}

MAX_FAILURES = 3
COOLDOWN = 120


def provider_available(name="groq"):
    state = _provider_state.setdefault(
        name,
        {"failures": 0, "blocked_until": 0}
    )

    return time.time() >= state["blocked_until"]


def provider_success(name="groq"):
    state = _provider_state[name]
    state["failures"] = 0
    state["blocked_until"] = 0


def provider_failure(name="groq"):
    state = _provider_state.setdefault(
        name,
        {"failures": 0, "blocked_until": 0}
    )

    state["failures"] += 1

    if state["failures"] >= MAX_FAILURES:
        state["blocked_until"] = time.time() + COOLDOWN


def status():
    return _provider_state
'''

p.write_text(content, encoding="utf-8")

print("AI Circuit Breaker created")
