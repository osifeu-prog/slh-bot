from unittest.mock import patch

import doctor_handler


def test_stale_federation_inventory_is_not_reported_as_live_service_failure():
    result = doctor_handler._federation_status_label({
        "verified_date_utc": "2026-09-21",
        "registry_age_days": 24,
        "registry_stale": True,
        "non_green": [
            {"project": "slh-os-control-plane", "service": "slh-mcp", "status": "DEPLOYING"},
            {"project": "diligent-radiance", "service": "slh-AI-bot", "status": "CRASHED"},
            {"project": "diligent-radiance", "service": "slh-fastapi", "status": "FAILED"},
            {"project": "TELEGRAM-BOT", "service": "Telegram_bot", "status": "FAILED"},
        ],
    })

    assert "INVENTORY STALE" in result
    assert "historical non-green snapshot entries=4" in result
    assert "not live status" in result
    assert "slh-AI-bot=CRASHED" in result


def test_fresh_non_green_federation_is_labelled_as_snapshot_not_heartbeat():
    result = doctor_handler._federation_status_label({
        "verified_date_utc": "2026-10-15",
        "registry_age_days": 0,
        "registry_stale": False,
        "non_green": [{"project": "legacy", "service": "old-bot", "status": "FAILED"}],
    })

    assert "snapshot has 1 non-green application entries" in result
    assert "not a live heartbeat" in result


def test_fresh_clean_federation_snapshot_is_scoped_as_snapshot():
    result = doctor_handler._federation_status_label({
        "verified_date_utc": "2026-10-15",
        "registry_age_days": 0,
        "registry_stale": False,
        "non_green": [],
    })

    assert result.startswith("🟢")
    assert "not a live heartbeat" in result


def test_deployment_commit_metadata_is_used_without_git_checkout():
    with patch.dict(
        "os.environ",
        {
            "RAILWAY_GIT_COMMIT_SHA": "abcdef0123456789",
            "RAILWAY_GIT_BRANCH": "main",
        },
        clear=True,
    ):
        result = doctor_handler._deployment_source_label()

    assert "deployed commit abcdef012345" in result
    assert "branch main" in result
    assert "לא ניתן לאמת Git" not in result


def test_overall_health_marks_stale_or_unknown_checks_as_degraded():
    assert "🟡" in doctor_handler._overall_health_label({
        "Federation inventory": "⚪️ INVENTORY STALE",
    })


def test_overall_health_does_not_hide_a_failed_check():
    assert "🔴" in doctor_handler._overall_health_label({
        "DB": "🔴 canonical state read failed",
        "Federation inventory": "🟢 snapshot has no non-green entries",
    })
