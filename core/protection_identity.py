from __future__ import annotations

from core.device_store import DeviceStore
from core.agent_state_store import AgentStateStore


class ProtectionIdentityError(ValueError):
    pass


class ProtectionIdentity:
    """Canonical validation for User -> Device -> Agent protection bindings."""

    def __init__(self, devices=None, agents=None):
        self.devices = devices or DeviceStore()
        self.agents = agents or AgentStateStore()

    def resolve_device(self, user_id: str, device_id: str) -> dict:
        user_id, device_id = str(user_id), str(device_id)
        device = self.devices.get(device_id)
        if not device:
            raise ProtectionIdentityError("DEVICE_NOT_FOUND")

        owner = device.get("owner_id")
        if owner is None:
            raise ProtectionIdentityError("PROTECTION_UNBOUND")

        if str(owner) != user_id:
            raise ProtectionIdentityError("DEVICE_OWNER_MISMATCH")

        return device

    def bind_agent(self, user_id: str, device_id: str, agent_id: str) -> dict:
        device = self.resolve_device(user_id, device_id)
        agent = self.agents.get(agent_id)
        if not agent:
            raise ProtectionIdentityError("AGENT_NOT_FOUND")

        agent_owner = agent.get("owner_id")
        if agent_owner is not None and str(agent_owner) != str(user_id):
            raise ProtectionIdentityError("AGENT_OWNER_MISMATCH")

        existing_device = agent.get("device_id")
        if existing_device is not None and str(existing_device) != str(device_id):
            raise ProtectionIdentityError("AGENT_ALREADY_BOUND")

        return {
            "user_id": str(user_id),
            "device_id": str(device_id),
            "agent_id": str(agent.get("id", agent_id)),
            "valid": True,
        }

    def validate_policy_owner(self, user_id: str, policy: dict) -> bool:
        if str(policy.get("user_id")) != str(user_id):
            raise ProtectionIdentityError("POLICY_OWNER_MISMATCH")

        device = self.resolve_device(user_id, policy.get("device_id"))
        if str(policy.get("user_id")) != str(device.get("owner_id")):
            raise ProtectionIdentityError("POLICY_DEVICE_OWNER_MISMATCH")

        return True
