import pytest

from core.protection_identity import ProtectionIdentity, ProtectionIdentityError


class Devices:
    def __init__(self, data):
        self.data = data

    def get(self, device_id):
        return self.data.get(str(device_id))


class Agents:
    def __init__(self, data):
        self.data = data

    def get(self, agent_id):
        return self.data.get(str(agent_id))


def resolver(devices, agents):
    return ProtectionIdentity(Devices(devices), Agents(agents))


def test_device_owner_is_required():
    r = resolver({"D1": {"device_id": "D1"}}, {})
    with pytest.raises(ProtectionIdentityError, match="PROTECTION_UNBOUND"):
        r.resolve_device("U1", "D1")


def test_device_owner_mismatch_fails_closed():
    r = resolver({"D1": {"device_id": "D1", "owner_id": "U2"}}, {})
    with pytest.raises(ProtectionIdentityError, match="DEVICE_OWNER_MISMATCH"):
        r.resolve_device("U1", "D1")


def test_agent_without_device_binding_is_not_implicitly_bound():
    r = resolver(
        {"D1": {"device_id": "D1", "owner_id": "U1"}},
        {"A1": {"id": "A1", "owner_id": "U1"}},
    )
    binding = r.bind_agent("U1", "D1", "A1")
    assert binding["valid"] is True


def test_agent_owned_by_another_user_fails():
    r = resolver(
        {"D1": {"device_id": "D1", "owner_id": "U1"}},
        {"A1": {"id": "A1", "owner_id": "U2"}},
    )
    with pytest.raises(ProtectionIdentityError, match="AGENT_OWNER_MISMATCH"):
        r.bind_agent("U1", "D1", "A1")


def test_existing_agent_binding_to_other_device_fails():
    r = resolver(
        {"D1": {"device_id": "D1", "owner_id": "U1"}},
        {"A1": {"id": "A1", "owner_id": "U1", "device_id": "D2"}},
    )
    with pytest.raises(ProtectionIdentityError, match="AGENT_ALREADY_BOUND"):
        r.bind_agent("U1", "D1", "A1")


def test_policy_owner_must_match_device_owner():
    r = resolver(
        {"D1": {"device_id": "D1", "owner_id": "U1"}},
        {},
    )
    with pytest.raises(ProtectionIdentityError, match="POLICY_OWNER_MISMATCH"):
        r.validate_policy_owner("U2", {"user_id": "U1", "device_id": "D1"})
