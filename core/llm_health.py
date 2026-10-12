"""Secret-free, best-effort LLM provider health telemetry for the owner control center."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any

HEALTH_PATH = Path("state/ai_health.json")
_ALLOWED_PROVIDERS = {"gemini", "groq", "ollama"}
_ALLOWED_STATUSES = {
    "HEALTHY",
    "RATE_LIMITED",
    "UNAVAILABLE",
    "COOLDOWN",
    "NOT_CONFIGURED",
    "ERROR",
}
_ALLOWED_REQUEST_STATUSES = {"HEALTHY", "DEGRADED"}
_ALLOWED_REASONS = {
    "request_succeeded",
    "quota_or_rate_limit",
    "api_key_missing",
    "provider_cooldown",
    "provider_error",
    "empty_response",
    "all_providers_failed",
    "unknown",
}
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_provider_result(provider: str, result: Any) -> tuple[str, str]:
    """Classify a provider result without retaining raw errors, prompts, or secrets."""
    provider = str(provider or "").strip().lower()
    value = str(result or "")
    upper = value.upper()
    lower = value.lower()

    if provider not in _ALLOWED_PROVIDERS:
        return "ERROR", "unknown"
    if upper in {"OLLAMA_NOT_CONFIGURED", "GEMINI_API_KEY MISSING", "GROQ_API_KEY MISSING"}:
        return "NOT_CONFIGURED", "api_key_missing" if provider != "ollama" else "unknown"
    if "NOT_CONFIGURED" in upper:
        return "NOT_CONFIGURED", "unknown"
    if "COOLDOWN" in upper:
        return "COOLDOWN", "provider_cooldown"
    if any(marker in lower for marker in ("429", "rate_limit", "rate limit", "quota", "tokens per day")):
        return "RATE_LIMITED", "quota_or_rate_limit"
    if not value.strip() or "EMPTY_RESPONSE" in upper:
        return "UNAVAILABLE", "empty_response"
    if upper.startswith(("GEMINI ERROR:", "LLM ERROR:", "OLLAMA_ERROR:", "OLLAMA_HTTP_")):
        return "UNAVAILABLE", "provider_error"
    return "HEALTHY", "request_succeeded"


def _read_unlocked(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and isinstance(value.get("providers", {}), dict):
            value.setdefault("schema_version", 1)
            value.setdefault("providers", {})
            value.setdefault("last_request", None)
            return value
    except (OSError, ValueError, TypeError):
        pass
    return {
        "schema_version": 1,
        "updated_at": None,
        "providers": {},
        "last_request": None,
    }


def _write_unlocked(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def record_provider_result(
    provider: str,
    status: str,
    *,
    model: str = "",
    reason_code: str = "unknown",
    path: Path | None = None,
) -> None:
    """Store bounded provider status only; failures must not affect an AI reply."""
    provider = str(provider or "").strip().lower()
    status = str(status or "ERROR").strip().upper()
    reason_code = str(reason_code or "unknown").strip().lower()
    if provider not in _ALLOWED_PROVIDERS:
        return
    if status not in _ALLOWED_STATUSES:
        status = "ERROR"
    if reason_code not in _ALLOWED_REASONS:
        reason_code = "unknown"
    target = Path(path) if path is not None else HEALTH_PATH
    entry = {
        "status": status,
        "model": str(model or "")[:80],
        "reason_code": reason_code,
        "checked_at": _now(),
    }
    try:
        with _LOCK:
            payload = _read_unlocked(target)
            payload.setdefault("providers", {})[provider] = entry
            payload["updated_at"] = entry["checked_at"]
            _write_unlocked(target, payload)
    except Exception:
        # Telemetry is deliberately best effort; never break conversation handling.
        return


def record_request_result(
    status: str,
    *,
    provider: str = "",
    reason_code: str = "unknown",
    path: Path | None = None,
) -> None:
    """Persist the last end-to-end LLM outcome without saving the prompt or answer."""
    status = str(status or "DEGRADED").strip().upper()
    if status not in _ALLOWED_REQUEST_STATUSES:
        status = "DEGRADED"
    provider = str(provider or "").strip().lower()
    if provider not in _ALLOWED_PROVIDERS:
        provider = ""
    reason_code = str(reason_code or "unknown").strip().lower()
    if reason_code not in _ALLOWED_REASONS:
        reason_code = "unknown"
    target = Path(path) if path is not None else HEALTH_PATH
    timestamp = _now()
    entry = {
        "status": status,
        "provider": provider,
        "reason_code": reason_code,
        "checked_at": timestamp,
    }
    try:
        with _LOCK:
            payload = _read_unlocked(target)
            payload["last_request"] = entry
            payload["updated_at"] = timestamp
            _write_unlocked(target, payload)
    except Exception:
        return


def load_health(path: Path | None = None) -> dict[str, Any]:
    """Read bounded health fields; never initiate a provider request."""
    target = Path(path) if path is not None else HEALTH_PATH
    try:
        with _LOCK:
            payload = _read_unlocked(target)
        providers = payload.get("providers", {})
        safe_providers = {}
        if isinstance(providers, dict):
            for name, item in providers.items():
                key = str(name).lower()
                if key not in _ALLOWED_PROVIDERS or not isinstance(item, dict):
                    continue
                status = str(item.get("status") or "UNKNOWN").upper()
                if status not in _ALLOWED_STATUSES:
                    status = "UNKNOWN"
                reason = str(item.get("reason_code") or "unknown").lower()
                if reason not in _ALLOWED_REASONS:
                    reason = "unknown"
                safe_providers[key] = {
                    "status": status,
                    "model": str(item.get("model") or "")[:80],
                    "reason_code": reason,
                    "checked_at": str(item.get("checked_at") or "")[:40],
                }
        request = payload.get("last_request")
        safe_request = None
        if isinstance(request, dict):
            status = str(request.get("status") or "UNKNOWN").upper()
            if status not in _ALLOWED_REQUEST_STATUSES:
                status = "UNKNOWN"
            provider = str(request.get("provider") or "").lower()
            if provider not in _ALLOWED_PROVIDERS:
                provider = ""
            reason = str(request.get("reason_code") or "unknown").lower()
            if reason not in _ALLOWED_REASONS:
                reason = "unknown"
            safe_request = {
                "status": status,
                "provider": provider,
                "reason_code": reason,
                "checked_at": str(request.get("checked_at") or "")[:40],
            }
        return {
            "schema_version": 1,
            "updated_at": str(payload.get("updated_at") or "")[:40] or None,
            "providers": safe_providers,
            "last_request": safe_request,
        }
    except Exception:
        return {
            "schema_version": 1,
            "updated_at": None,
            "providers": {},
            "last_request": None,
        }
