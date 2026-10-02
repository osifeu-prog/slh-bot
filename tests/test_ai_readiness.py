"""Regression coverage for the read-only AI readiness model."""

import os

from core import ai_readiness


def test_ai_readiness_reports_route_without_exposing_credentials(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret-test")
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret-test")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    snapshot = ai_readiness.snapshot()

    assert snapshot["read_only"] is True
    assert snapshot["network_probe"] is False
    assert snapshot["source_of_truth"] == "state/db.json"
    assert snapshot["provider_route"] == ["gemini", "ollama", "groq"]
    assert snapshot["providers"]["gemini"]["configured"] is True
    assert snapshot["providers"]["groq"]["configured"] is True
    assert snapshot["providers"]["ollama"]["configured"] is False
    assert "gemini-secret-test" not in str(snapshot)
    assert "groq-secret-test" not in str(snapshot)
    assert "canonical_state" in snapshot["layers"]
    assert "conversation_memory" in snapshot["layers"]


def test_ai_readiness_without_provider_is_unavailable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    snapshot = ai_readiness.snapshot()

    assert snapshot["status"] == "UNAVAILABLE"
    assert snapshot["active_providers"] == []
