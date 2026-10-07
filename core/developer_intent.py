"""Safe read-only intent inspections for the Telegram Developer command.

This module never executes shell commands, mutates state, opens gates, or deploys.
It only inspects known source files and the already-running TeleBot instance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.runtime_command_evidence import snapshot_bot


ROOT = Path(__file__).resolve().parents[1]


def normalize_intent(raw: str) -> str | None:
    text = " ".join(str(raw or "").strip().lower().split())
    if not text:
        return None

    investor_markers = ("investor", "overview", "משקיע", "משקיעים")
    if "investor" in text and "overview" in text:
        return "investor_overview"
    if any(marker in text for marker in investor_markers) and (
        "overview" in text or "סקירה" in text
    ):
        return "investor_overview"

    command_markers = (
        "command",
        "commands",
        "פקודה",
        "פקודות",
        "collision",
        "collisions",
        "התנגש",
    )
    if any(marker in text for marker in command_markers):
        return "runtime_commands"

    return None


def _read_source(path: str) -> str:
    candidate = (ROOT / path).resolve()
    if candidate == ROOT or ROOT not in candidate.parents:
        raise ValueError("INVALID_SOURCE_PATH")
    if not candidate.is_file():
        return ""
    return candidate.read_text(encoding="utf-8", errors="replace")


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def inspect_investor_overview() -> dict[str, Any]:
    read_model = _read_source("core/investor_read_model.py")
    onboarding = _read_source("handlers/onboarding_v2.py")
    mini_app = _read_source("mini_app.html")
    webapp = _read_source("webapp.py")

    checks = {
        "canonical_read_model": "def get_investor_snapshot" in read_model,
        "telegram_button_or_callback": _contains_any(
            onboarding,
            (
                "callback_data=\"investor_overview\"",
                "callback_data='investor_overview'",
            ),
        ),
        "mini_app_screen": _contains_any(
            mini_app,
            (
                'id="investor"',
                "show('investor')",
                'show("investor")',
                "screen=investor",
            ),
        ),
        "me_api": "/api/v1/me" in webapp,
    }

    if not checks["canonical_read_model"]:
        status = "blocked"
        next_step = "Investor read-model is missing."
    elif checks["telegram_button_or_callback"] and checks["mini_app_screen"]:
        status = "ready"
        next_step = "Both Telegram and Mini App surfaces are present."
    else:
        status = "partial"
        missing = []
        if not checks["telegram_button_or_callback"]:
            missing.append("Telegram Investor callback/button")
        if not checks["mini_app_screen"]:
            missing.append("Mini App screen=investor")
        next_step = "Missing: " + ", ".join(missing) + "."

    return {
        "intent": "investor_overview",
        "status": status,
        "checks": checks,
        "next_step": next_step,
        "source": "deployed repository files (read-only)",
    }


def inspect_runtime_commands(bot: object) -> dict[str, Any]:
    evidence = snapshot_bot("Me_ad_main", bot)
    return {
        "intent": "runtime_commands",
        "status": "ok",
        "total_handlers": evidence.get("total_message_handlers", 0),
        "command_registrations": evidence.get("command_registrations", 0),
        "unique_commands": evidence.get("unique_commands", 0),
        "collision_count": evidence.get("collision_count", 0),
        "collisions": evidence.get("collisions", {}),
        "source": evidence.get("source"),
    }


def inspect(raw: str, bot: object) -> dict[str, Any]:
    intent = normalize_intent(raw)
    if intent == "investor_overview":
        return inspect_investor_overview()
    if intent == "runtime_commands":
        return inspect_runtime_commands(bot)
    raise ValueError("UNKNOWN_DEV_INTENT")
