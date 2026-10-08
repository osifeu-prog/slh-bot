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
