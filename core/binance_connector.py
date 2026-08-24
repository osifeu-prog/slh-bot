"""
SLH Binance / BSC Connector
"""
import os
import json

BSC_DEFAULTS = {
    "network": "bsc",
    "rpc": "https://bsc-dataseed.binance.org/",
    "chain_id": 56,
    "symbol": "BNB",
    "explorer": "https://bscscan.com",
    "token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
}

def get_bsc_config():
    raw = os.getenv("SLH_BSC_CONFIG")
    if raw:
        try:
            return {**BSC_DEFAULTS, **json.loads(raw)}
        except Exception:
            pass
    return BSC_DEFAULTS

def has_binance_credentials():
    api = os.getenv("BINANCE_API_KEY") or ""
    secret = os.getenv("BINANCE_SECRET") or ""
    return len(api) >= 10 and api != "..." and len(secret) >= 10 and secret != "..."

def get_ton_wallet():
    wallet = os.getenv("TON_WALLET")
    if wallet and wallet not in ("...", ""):
        return wallet
    try:
        import json
        from pathlib import Path
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        return db.get("ton_settings", {}).get("wallet")
    except Exception:
        return None

def status():
    return {
        "bsc_config": get_bsc_config(),
        "binance_credentials": has_binance_credentials(),
        "ton_wallet": bool(get_ton_wallet()),
    }
