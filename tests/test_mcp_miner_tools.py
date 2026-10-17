from unittest.mock import patch

import pytest

from slh_mcp.auth import Principal
from slh_mcp.capabilities import get_capability
from slh_mcp.tools import miners as miner_tools


OWNER = Principal(
    subject="8789977826",
    role="OWNER",
    permissions=frozenset({"exec.audit"}),
)


def test_miner_mcp_capabilities_are_read_only_and_audit_gated():
    listing = get_capability("miners.list")
    status = get_capability("miners.status")
    assert listing.mutating is False
    assert status.mutating is False
    assert listing.permission == "exec.audit"
    assert status.permission == "exec.audit"


def test_mcp_miners_list_uses_existing_authenticated_bridge():
    expected = {
        "count": 1,
        "read_only": True,
        "devices": [{
            "device_id": "ESP_1787680517",
            "status": "online",
            "miner_enabled": False,
            "telemetry": None,
        }],
    }
    with patch("slh_mcp.tools.miners.authorize", return_value=True), patch(
        "slh_mcp.tools.miners.control_plane_client.miners", return_value=expected
    ) as bridge:
        assert miner_tools.miners_list(OWNER) == expected
    bridge.assert_called_once_with()


def test_mcp_miner_status_reads_one_device_without_writing():
    expected = {
        "device_id": "ESP_1787680517",
        "status": "online",
        "read_only": True,
        "telemetry": {"temperature_c": 68.5, "watts": 3250.0},
    }
    with patch("slh_mcp.tools.miners.authorize", return_value=True), patch(
        "slh_mcp.tools.miners.control_plane_client.miner", return_value=expected
    ) as bridge:
        assert miner_tools.miner_status("ESP_1787680517", OWNER) == expected
    bridge.assert_called_once_with("ESP_1787680517")


def test_mcp_miner_tool_denies_principal_without_exec_audit():
    with patch("slh_mcp.tools.miners.authorize", return_value=False), patch(
        "slh_mcp.tools.miners.control_plane_client.miners"
    ) as bridge:
        with pytest.raises(PermissionError, match="MINER_STATUS_FORBIDDEN"):
            miner_tools.miners_list(OWNER)
    bridge.assert_not_called()


def test_mcp_miner_status_requires_device_id():
    with patch("slh_mcp.tools.miners.authorize", return_value=True), patch(
        "slh_mcp.tools.miners.control_plane_client.miner"
    ) as bridge:
        with pytest.raises(ValueError, match="device_id required"):
            miner_tools.miner_status("", OWNER)
    bridge.assert_not_called()



def test_mcp_registry_registers_both_miner_read_tools():
    from unittest.mock import Mock
    from slh_mcp import registry

    server = Mock()
    with patch("slh_mcp.registry.register_resources"), patch(
        "slh_mcp.registry.register_extended_resources"
    ), patch("slh_mcp.registry.register_economic_resources"), patch(
        "slh_mcp.registry.register_infrastructure_resources"
    ), patch("slh_mcp.resources.register_mqtt_resources"):
        registry.register_capabilities(server)

    registered_names = {
        call.kwargs.get("name")
        for call in server.add_tool.call_args_list
    }
    assert "miners.list" in registered_names
    assert "miners.status" in registered_names
