"""Canonical production runtime registry.

Read-only metadata used by the SLH Control Plane. It separates repositories
that belong to the ecosystem; it does not imply one shared runtime or state store.
"""

RUNTIMES = {
    "wallet-bot": {
        "repository": "osifeu-prog/slh-master-bot",
        "branch": "main",
        "railway_project": "SLH_investor_wallet_bot",
        "railway_project_id": "b89a959c-e6ec-4e28-b7a9-818bc13307de",
        "railway_service": "slh-bot",
        "railway_service_id": "f17cc606-840a-49ff-aea0-dad051bd8fac",
        "environment": "production",
        "purpose": "Telegram wallet/economy bot",
        "canonical": True,
    },
    "api": {
        "repository": "osifeu-prog/slh-api",
        "branch": "master",
        "railway_project": "slh-api",
        "railway_project_id": "96452076-6885-4e6d-9b26-9ef20d6c3cd7",
        "railway_service": "slh-api",
        "railway_service_id": "bcbb5f6a-f0a1-4547-a85b-b8462985cdce",
        "environment": "production",
        "purpose": "Canonical SLH API",
        "canonical": True,
    },
    "website": {
        "repository": "osifeu-prog/SLH.co.il",
        "branch": "main",
        "railway_project": "diligent-radiance",
        "railway_project_id": "97070988-27f9-4e0f-b76c-a75b5a7c9673",
        "railway_service": "SLH.co.il",
        "railway_service_id": "63471580-d05a-41fc-a7bb-d90ac488abfd",
        "environment": "production",
        "purpose": "Public website and Web UI",
        "canonical": True,
    },
    "ai-bot": {
        "repository": "osifeu-prog/slh-claude-bot",
        "branch": "main",
        "railway_project": "diligent-radiance",
        "railway_project_id": "97070988-27f9-4e0f-b76c-a75b5a7c9673",
        "railway_service": "slh-AI-bot",
        "railway_service_id": "06b914f7-3e5f-4d35-82b2-5efd80fdca6a",
        "environment": "production",
        "purpose": "AI runtime",
        "canonical": True,
    },
    "legacy-telegram": {
        "repository": "osifeu-prog/telegram-bot",
        "branch": "main",
        "railway_project": "TELEGRAM-BOT",
        "railway_project_id": "89d74faf-fa5e-402e-a337-ca1365b04ba7",
        "railway_service": "Telegram_bot",
        "railway_service_id": "7f8ea87c-8b8b-4b22-9e2e-10525709eced",
        "environment": "production",
        "purpose": "Legacy Telegram webhook runtime",
        "canonical": False,
    },
    "control-plane-source": {
        "repository": "osifeu-prog/slh-bot",
        "branch": "main",
        "railway_project": None,
        "railway_project_id": None,
        "railway_service": None,
        "railway_service_id": None,
        "environment": None,
        "purpose": "Control Plane source and integration code; not the wallet runtime",
        "canonical": False,
    },
}


def get_runtime(runtime_id):
    return dict(RUNTIMES[runtime_id])


def list_runtimes():
    return [dict(runtime, runtime_id=runtime_id) for runtime_id, runtime in RUNTIMES.items()]
