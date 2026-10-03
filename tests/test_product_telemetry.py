"""Unit tests for the privacy-safe product telemetry adapter."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from core import product_telemetry


def test_emit_writes_valid_event_without_sensitive_fields():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.jsonl"
        with patch.object(product_telemetry, "log_event") as logger:
            logger.return_value = True
            ok = product_telemetry.emit(
                event="onboarding.join_completed",
                actor_key="user:123",
                flow="onboarding",
                surface="telegram",
                result="success",
                journey_id="ONBOARDING_V1",
                duration_ms=25,
                app_version="test",
            )

        assert ok is True
        assert logger.call_args.args[0] == "onboarding.join_completed"
        details = logger.call_args.kwargs["details"]
        assert details["actor_key"] == "user:123"
        assert details["duration_ms"] == 25
        assert "message" not in details
        assert "name" not in details
        assert "wallet_address" not in details
        assert "payment_id" not in details
        assert "balance" not in details
        assert "transaction_hash" not in details


def test_emit_rejects_invalid_result():
    with patch.object(product_telemetry, "log_event") as logger:
        assert product_telemetry.emit(
            event="onboarding.join_completed",
            actor_key="user:123",
            flow="onboarding",
            surface="telegram",
            result="anything_else",
            journey_id="ONBOARDING_V1",
        ) is False
        logger.assert_not_called()


def test_emit_is_best_effort():
    with patch.object(product_telemetry, "log_event", side_effect=RuntimeError("audit down")):
        assert product_telemetry.emit(
            event="onboarding.join_completed",
            actor_key="user:123",
            flow="onboarding",
            surface="telegram",
            result="success",
            journey_id="ONBOARDING_V1",
        ) is False
