"""Non-secret Telegram bot ownership and Railway target registry.

Raw Telegram tokens must never be stored here. Each entry identifies the
intended bot username and the Railway service variable(s) that consume its
token.
"""

from __future__ import annotations

from copy import deepcopy


_BOT_REGISTRY = {
    "main": {
        "alias": "main",
        "username": "Me_ad_main_bot",
        "label": "SLH Control Plane",
        "targets": [
            {
                "project": "endearing-amazement",
                "project_id": "fd30fefb-3d35-48a5-a7cb-e05337e812f4",
                "environment": "production",
                "environment_id": "661caa13-83cb-4197-8825-943bebf96c5a",
                "service": "web",
                "service_id": "13d97581-0199-4f6a-80d1-885c9304ffc5",
                "variable": "BOT_TOKEN",
            }
        ],
    },
    "air": {
        "alias": "air",
        "username": "SLH_AIR_bot",
        "label": "SLH AIR",
        "targets": [
            {
                "project": "slh-api",
                "project_id": "96452076-6885-4e6d-9b26-9ef20d6c3cd7",
                "environment": "production",
                "environment_id": "82f92047-5350-4082-a11b-eb07c64cf0fd",
                "service": "slh-air-bot",
                "service_id": "33dc3f7c-e50b-4345-a78a-6132468fddf5",
                "variable": "TELEGRAM_TOKEN",
            }
        ],
    },
    "claude": {
        "alias": "claude",
        "username": "SLH_Claude_bot",
        "label": "SLH AI",
        "targets": [
            {
                "project": "diligent-radiance",
                "project_id": "97070988-27f9-4e0f-b76c-a75b5a7c9673",
                "environment": "production",
                "environment_id": "e0a8a279-4dc2-4461-8ba6-d16594d6ceca",
                "service": "slh-AI-bot",
                "service_id": "06b914f7-3e5f-4d35-82b2-5efd80fdca6a",
                "variable": "SLH_CLAUDE_BOT_TOKEN",
            }
        ],
    },
    "taxfree": {
        "alias": "taxfree",
        "username": "Tax_Free_world_bot",
        "label": "Tax Free World",
        "targets": [
            {
                "project": "Tax_Free_world_bot",
                "project_id": "8023b98a-8241-4b7a-8e53-f3e4ff32547a",
                "environment": "production",
                "environment_id": "e6c6b1bf-9903-4165-9fe3-010d9e187972",
                "service": "Tax_Free_world_bot",
                "service_id": "5c96141d-c07a-4b5c-80b3-72946893acc9",
                "variable": "BOT_TOKEN",
            }
        ],
    },
    "ton": {
        "alias": "ton",
        "username": "TON_MNH_bot",
        "label": "TON / MNH",
        "targets": [
            {
                "project": "dazzling-unity",
                "project_id": "e05a2fea-7667-4b10-a159-f6e8976a2931",
                "environment": "production",
                "environment_id": "d6f52e43-fc69-49e7-9405-ae2c0f8653ea",
                "service": "SLH_PROJECT_V2",
                "service_id": "46b50f17-0165-41f2-9fe7-bcac40e1681a",
                "variable": "BOT_TOKEN",
            },
            {
                "project": "dazzling-unity",
                "project_id": "e05a2fea-7667-4b10-a159-f6e8976a2931",
                "environment": "production",
                "environment_id": "d6f52e43-fc69-49e7-9405-ae2c0f8653ea",
                "service": "glorious-caring",
                "service_id": "9c2fa5e0-4930-405f-8647-5f0ede06ff26",
                "variable": "BOT_TOKEN",
            },
        ],
    },
}


def list_bots() -> list[dict]:
    return deepcopy(list(_BOT_REGISTRY.values()))


def get_bot(alias: str) -> dict:
    key = (alias or "").strip().lower()
    if key not in _BOT_REGISTRY:
        raise KeyError(key)
    return deepcopy(_BOT_REGISTRY[key])


def targets_for(alias: str) -> list[dict]:
    return get_bot(alias)["targets"]