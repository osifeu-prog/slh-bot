"""Unified SLH System map exposed through the central Control Plane.

Read-only: this command reports the federation of the central bot, API,
Mini App/website, exchange/economy modules, and separately deployed clients.
It does not mutate state or move funds.
"""
from datetime import datetime, timezone

SYSTEMS = [
    {"id":"central_gateway","name":"SLH OS Central Gateway","role":"control_plane","repo":"osifeu-prog/slh-bot","railway_project":"slh-api","service":"slh-api"},
    {"id":"air_bot","name":"SLH AIR Bot","role":"client_bot","railway_project":"slh-api","service":"slh-air-bot"},
    {"id":"main_web","name":"SLH Web / Mini App","role":"client_ui","hosted_by":"central_gateway","routes":["/dashboard","/mini-app"]},
    {"id":"api","name":"Flask API","role":"shared_backend","hosted_by":"central_gateway","routes":["/api/v1/me","/api/wallet/bnb","/api/v1/exchange"]},
    {"id":"exchange","name":"SLH Internal Exchange","role":"economy_service","module":"handlers.exchange_handler","market":"SLH/CREDITS"},
    {"id":"wallet_binding","name":"BNB Wallet Binding","role":"identity_binding","module":"core.wallet_binding","routes":["/api/wallet/bnb/challenge","/api/wallet/bnb/verify"]},
    {"id":"legacy_migration","name":"Legacy Wallet Migration","role":"migration_registry","module":"core.legacy_wallet_migration"},
    {"id":"investor_client","name":"SLH Investor Wallet Bot","role":"legacy_external_client","railway_project":"SLH_investor_wallet_bot","service":"slh-bot","integration_status":"isolated_until_adapter"},
    {"id":"telegram_legacy","name":"TELEGRAM-BOT","role":"legacy_external_client","railway_project":"TELEGRAM-BOT","service":"Telegram_bot","integration_status":"isolated_until_adapter"},
    {"id":"cloud_legacy","name":"slh-cloud-bot","role":"legacy_external_client","railway_project":"slh-cloud-bot","service":"slh-cloud-bot","integration_status":"isolated_until_adapter"},
    {"id":"public_site","name":"slh.co.il","role":"public_site","railway_project":"slh.co.il","integration_status":"site_level_integration_pending"},
]

def get_unified_map():
    return {
        "schema_version":"1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "control_plane":"central_gateway",
        "canonical_repo":"osifeu-prog/slh-bot",
        "canonical_state":"state/db.json",
        "systems":SYSTEMS,
        "principles":[
            "Central bot is the operational Control Plane.",
            "Website, Mini App and secondary bots are clients/adapters, not competing state authorities.",
            "No client may mint, settle, or mutate canonical balances outside the central economy authority.",
            "Wallet binding proves identity; it does not itself credit funds.",
            "External token conversion requires an explicit verified settlement path.",
        ],
    }

def register(bot):
    @bot.message_handler(commands=["unified_map"])
    def unified_map(msg):
        m=get_unified_map()
        lines=["🗺 SLH UNIFIED SYSTEM","",f"Control Plane: {m['control_plane']}",f"Canonical state: {m['canonical_state']}",""]
        for s in m["systems"]:
            status=s.get("integration_status","central")
            lines.append(f"• {s['name']} — {s['role']} — {status}")
        lines += ["","Use /system for the operational snapshot."]
        bot.reply_to(msg,"\n".join(lines))
