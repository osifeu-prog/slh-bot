from unittest.mock import patch

from core import command_catalog


def test_catalog_uses_runtime_as_source_of_truth():
    runtime = {
        "commands": ["/start", "/mystery"],
    }

    with patch(
        "core.runtime_command_evidence.snapshot_runtime",
        return_value=runtime,
    ):
        catalog = command_catalog.get_catalog("Me_ad_main")

    by_command = {item["command"]: item for item in catalog}

    assert by_command["start"]["category"] == "ACCOUNT"
    assert by_command["start"]["known"] is True

    assert by_command["mystery"]["category"] == "UNCLASSIFIED"
    assert by_command["mystery"]["known"] is False


def test_catalog_is_presentation_only_and_does_not_add_commands():
    runtime = {
        "commands": ["/start"],
    }

    with patch(
        "core.runtime_command_evidence.snapshot_runtime",
        return_value=runtime,
    ):
        catalog = command_catalog.get_catalog("Me_ad_main")

    assert [item["command"] for item in catalog] == ["start"]
    assert "deploy" not in {item["command"] for item in catalog}


def test_render_help_prioritizes_known_commands_before_unknown_tail():
    known_commands = [
        "/start",
        "/trade",
        "/wallet",
        "/stake",
        "/check",
        "/exchange",
    ]
    unknown_commands = [f"/unknown_{index:03d}" for index in range(100)]
    runtime = {"commands": unknown_commands + known_commands}

    with patch(
        "core.runtime_command_evidence.snapshot_runtime",
        return_value=runtime,
    ):
        rendered = command_catalog.render_help("Me_ad_main", limit=5)

    for command in known_commands:
        assert f"/{command.lstrip('/')} — " in rendered

    assert "… ועוד 100 פקודות runtime ללא מטא־דאטה" in rendered
    assert len(rendered) < 4096


def test_help_metadata_covers_existing_runtime_commands():
    commands = [
        "/check_ux",
        "/check_bnb_deposits",
        "/bnb_reverse_prepare",
        "/bnb_reverse_confirm",
        "/bnb_reverse_cancel",
        "/biz",
        "/biz_users",
        "/biz_revenue",
        "/biz_ai",
        "/biz_bots",
        "/bots",
        "/execr",
        "/bnb_smoke",
        "/academy_progress",
    ]

    with patch(
        "core.runtime_command_evidence.snapshot_runtime",
        return_value={"commands": commands},
    ):
        catalog = command_catalog.get_catalog("Me_ad_main")

    by_command = {item["command"]: item for item in catalog}
    assert set(by_command) == {command.lstrip("/") for command in commands}
    assert all(item["known"] for item in by_command.values())
    assert all(item["description"] != "Runtime command — metadata pending" for item in by_command.values())


def test_exchange_status_alias_has_catalog_metadata():
    commands = ["/exchange_status"]

    with patch(
        "core.runtime_command_evidence.snapshot_runtime",
        return_value={"commands": commands},
    ):
        catalog = command_catalog.get_catalog("Me_ad_main")

    by_command = {item["command"]: item for item in catalog}
    item = by_command["exchange_status"]
    assert item["known"] is True
    assert "Exchange" in item["description"]

def test_public_help_uses_real_line_breaks_and_includes_core_shortcuts():
    runtime = {
        "commands": [
            "/start",
            "/help",
            "/balance",
            "/history",
            "/dashboard",
            "/progress",
        ],
    }

    with patch(
        "core.runtime_command_evidence.snapshot_runtime",
        return_value=runtime,
    ):
        rendered = command_catalog.render_public_help("Me_ad_main")

    assert "\\\\n" not in rendered
    assert "\n/start — כניסה והתחלה" in rendered
    assert "/balance — יתרת Credits" in rendered
    assert "/history — היסטוריית עסקאות" in rendered
    assert "/dashboard — לוח הבקרה" in rendered
    assert "/progress — התקדמות אישית" in rendered
