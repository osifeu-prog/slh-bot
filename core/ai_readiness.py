"""Read-only AI readiness model for SLH OS.

Reports configuration/runtime readiness without provider network calls, spending
provider quota, exposing secrets, or mutating state.
"""

from __future__ import annotations

import os
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _configured(name: str) -> bool:
    return bool((os.getenv(name) or "").strip().strip("\"'"))


def _cooldown_snapshot() -> dict:
    try:
        from handlers import llm_handler

        now = time.time()
        cloud = getattr(llm_handler, "_provider_cooldown_until", {}) or {}
        ollama_until = float(
            getattr(llm_handler, "_OLLAMA_COOLDOWN_UNTIL", 0.0) or 0.0
        )
        return {
            "gemini": max(0, int(float(cloud.get("gemini", 0) or 0) - now)),
            "groq": max(0, int(float(cloud.get("groq", 0) or 0) - now)),
            "ollama": max(0, int(ollama_until - now)),
        }
    except Exception as exc:
        return {
            "gemini": 0,
            "groq": 0,
            "ollama": 0,
            "error": type(exc).__name__,
        }


def _layer_contracts() -> dict:
    paths = {
        "canonical_state": ROOT / "state" / "db.json",
        "command_registry": ROOT / "core" / "command_registry.py",
        "faq": ROOT / "core" / "faq_service.py",
        "conversation_memory": ROOT / "core" / "conversation_memory.py",
        "trust_router": ROOT / "core" / "trust_router.py",
        "ask_router": ROOT / "core" / "ask_router.py",
        "ai_intake": ROOT / "core" / "ai_intake.py",
        "memory_db": ROOT / "memory.db",
    }
    return {name: path.is_file() for name, path in paths.items()}


def snapshot() -> dict:
    cooldowns = _cooldown_snapshot()
    layers = _layer_contracts()

    providers = {
        "gemini": {
            "configured": _configured("GEMINI_API_KEY"),
            "model": (os.getenv("GEMINI_MODEL") or "").strip() or "auto/default",
            "cooldown_seconds": cooldowns.get("gemini", 0),
        },
        "ollama": {
            "configured": bool((os.getenv("OLLAMA_BASE_URL") or "").strip()),
            "model": (os.getenv("OLLAMA_MODEL") or "").strip() or "qwen3:8b",
            "cooldown_seconds": cooldowns.get("ollama", 0),
        },
        "groq": {
            "configured": _configured("GROQ_API_KEY"),
            "model": "openai/gpt-oss-20b",
            "cooldown_seconds": cooldowns.get("groq", 0),
        },
    }

    active_providers = [
        name
        for name, provider in providers.items()
        if provider["configured"] and provider["cooldown_seconds"] == 0
    ]

    critical_layers = {
        "canonical_state",
        "command_registry",
        "faq",
        "conversation_memory",
        "trust_router",
        "ask_router",
        "ai_intake",
        "memory_db",
    }
    layers_ok = all(layers.get(name) for name in critical_layers)

    if active_providers and layers_ok:
        status = "READY"
    elif active_providers:
        status = "DEGRADED"
    else:
        status = "UNAVAILABLE"

    return {
        "status": status,
        "provider_route": ["gemini", "ollama", "groq"],
        "active_providers": active_providers,
        "providers": providers,
        "layers": layers,
        "source_of_truth": "state/db.json",
        "read_only": True,
        "network_probe": False,
        "note": "Credentials are reported only as configured/not configured; secrets are never returned.",
    }
