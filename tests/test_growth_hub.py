from pathlib import Path


def test_growth_hub_is_read_only_and_composes_existing_rails():
    src = Path("core/growth_hub.py").read_text(encoding="utf-8")
    assert "def build_growth_hub(uid)" in src
    assert "record_transaction" not in src
    assert "record_stars_payment" not in src
    assert "settle_" not in src


def test_growth_hub_endpoint_is_authenticated():
    src = Path("webapp.py").read_text(encoding="utf-8")
    marker = '@app.route("/api/v1/growth-hub")'
    assert marker in src
    section = src[src.index(marker):]
    assert "authenticated_uid()" in section


def test_growth_events_are_whitelisted_and_idempotent():
    src = Path("webapp.py").read_text(encoding="utf-8")
    marker = '@app.route("/api/v1/growth-events", methods=["POST"])'
    assert marker in src
    section = src[src.index(marker):]
    assert "ALLOWED_GROWTH_EVENTS" in section
    assert "event_id" in section
    assert "growth_events" in section


def test_mini_app_renders_growth_hub_and_tracks_core_actions():
    src = Path("mini_app.html").read_text(encoding="utf-8")
    assert 'id="growthHub"' in src
    assert "loadGrowthHub" in src
    assert "/api/v1/growth-hub" in src
    assert "/api/v1/growth-events" in src