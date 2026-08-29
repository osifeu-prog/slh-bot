"""
SLH Morning Brief v1
Source of truth: state/db.json + daily_plan.json + onchain
"""
import json
import requests
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


def _load_db():
    return json.loads(Path("state/db.json").read_text(encoding="utf-8"))


def get_daily_plan():
    p = Path("state/daily_plan.json")
    if not p.exists():
        return {"goals": [], "focus": "none"}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"goals": [], "focus": "none"}


def get_surf_forecast():
    try:
        url = "https://marine-api.open-meteo.com/v1/marine"
        params = {
            "latitude": 32.321,
            "longitude": 34.853,
            "hourly": "wave_height,wind_wave_height",
            "forecast_days": 1,
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        waves = data.get("hourly", {}).get("wave_height", [])
        current = waves[-1] if waves else "N/A"
        return {
            "beach": "נתניה",
            "wave_height_m": current,
            "note": "מקור: Open-Meteo Marine",
        }
    except Exception as e:
        return {
            "beach": "נתניה",
            "wave_height_m": "N/A",
            "note": f"שגיאת חיבור: {str(e)[:80]}",
        }


def get_morning_brief(uid):
    db = _load_db()
    user = db.get("users", {}).get(str(uid), {})
    wallet = user.get("wallet", {})
    plan = get_daily_plan()
    surf = get_surf_forecast()

    try:
        from core.deposit_monitor import get_onchain_status
        onchain = get_onchain_status()
    except Exception as e:
        onchain = {"error": str(e)}

    lines = [
        "בס״ד",
        "",
        "🌅 דוח פתיחת יום SLH",
        f"🕒 {datetime.now(ZoneInfo('Asia/Jerusalem')).isoformat()}",
        f"👤 {user.get('name') or 'User'}",
        f"💰 Credits: {wallet.get('credits', 0)}",
        f"🔒 Staked: {wallet.get('staked', 0)}",
        f"🪙 Token: {wallet.get('token_balance', 0)}",
        "",
        "📌 תוכנית היום:",
    ]
    for g in plan.get("goals", []):
        lines.append(f"• {g}")

    lines += [
        "",
        "🌊 תחזית גלים:",
        f"• {surf.get('beach')}: {surf.get('wave_height_m')}",
        f"• {surf.get('note')}",
        "",
        "📡 Onchain:",
        f"• BNB Treasury: {onchain.get('treasury_bnb')}",
        f"• SLH Treasury: {onchain.get('treasury_slh')}",
        f"• Block: {onchain.get('block')}",
        "",
        "💡 פעולה ראשונה: /wallet || /onchain",
    ]
    return "\n".join(lines)
