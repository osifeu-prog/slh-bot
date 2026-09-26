"""Read-only revenue, growth and rewards hub for the authenticated user.

This module composes already-existing authorities. It never mutates balances,
creates rewards, settles payments, signs transactions, or changes wallet state.
"""

from pathlib import Path
import json
import os
import time

import state_manager
from core import revenue_ledger
from core.authority import has_permission
from core.bnb_gate import bnb_deposits_open
from core.wallet_binding import get_binding
from core.ton_wallet_binding import get_ton_binding
from core.ton_deposit_service import deposits_are_open as ton_deposits_open
from core.stars_price_authority import CREDIT_PACKS, VIP_MONTHLY_STARS
from store.engine import load_items
from store.stars_purchase_service import get_stars_items

REWARD_LEDGER_FILE = Path("state/rewards_ledger.json")


def _num(value, default=0):
    return float(value) if isinstance(value, (int, float)) else float(default)


def _reward_totals(uid):
    points = 0.0
    credits = 0.0
    entries = 0
    if not REWARD_LEDGER_FILE.exists():
        return {"points": points, "credits": credits, "entries": entries}
    try:
        data = json.loads(REWARD_LEDGER_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"points": points, "credits": credits, "entries": entries}
    if not isinstance(data, list):
        return {"points": points, "credits": credits, "entries": entries}
    for row in data:
        if not isinstance(row, dict) or str(row.get("user")) != str(uid):
            continue
        p = row.get("points")
        c = row.get("credits")
        if isinstance(p, (int, float)):
            points += float(p)
        if isinstance(c, (int, float)):
            credits += float(c)
        if p or c:
            entries += 1
    return {"points": points, "credits": credits, "entries": entries}


def _academy_progress(user):
    academy = user.get("academy", {}) if isinstance(user.get("academy"), dict) else {}
    courses = academy.get("courses", {}) if isinstance(academy.get("courses"), dict) else {}
    completed_lessons = 0
    enrolled = len(courses)
    for course in courses.values():
        if not isinstance(course, dict):
            continue
        done = course.get("completed", [])
        if isinstance(done, list):
            completed_lessons += len(done)
    return {"enrolled_courses": enrolled, "completed_lessons": completed_lessons}


def build_growth_hub(uid):
    uid = str(uid)
    db = state_manager.load_db()
    users = db.get("users", {}) if isinstance(db.get("users"), dict) else {}
    user = users.get(uid)
    if not isinstance(user, dict):
        raise ValueError("USER_NOT_FOUND")

    wallet = user.get("wallet", {}) if isinstance(user.get("wallet"), dict) else {}
    referral = user.get("referral", {}) if isinstance(user.get("referral"), dict) else {}
    gamification = user.get("gamification", {}) if isinstance(user.get("gamification"), dict) else {}
    reward_totals = _reward_totals(uid)
    academy = _academy_progress(user)

    completed_tasks = 0
    open_tasks = 0
    tasks = db.get("tasks", {}) if isinstance(db.get("tasks"), dict) else {}
    for task_id, task in tasks.items():
        if not isinstance(task, dict) or str(task.get("owner_id", "")) != uid:
            continue
        done_by = task.get("done_by", [])
        done = uid in [str(x) for x in done_by] if isinstance(done_by, list) else False
        status = "done" if done else str(task.get("status", "open"))
        if status == "done":
            completed_tasks += 1
        else:
            open_tasks += 1

    stars_items = get_stars_items()
    items = load_items()
    stars_catalog = []
    pack_prices = ", ".join(str(p.stars) for p in CREDIT_PACKS)
    pack_prices = ", ".join(str(p.stars) for p in CREDIT_PACKS)
    for item_id, price in stars_items.items():
        item = items.get(item_id, {})
        if not isinstance(item, dict):
            item = {}
        stars_catalog.append({
            "id": str(item_id),
            "name": str(item.get("name", item_id)),
            "stars": int(price),
            "type": str(item.get("type", "digital")),
        })
    vip_expires_at = int(user.get("vip_access_until", 0) or 0)
    vip_active = vip_expires_at > int(time.time())

    try:
        from core.card_payment_service import card_payments_status, get_card_items
        card_status = card_payments_status()
        card_items = get_card_items() if card_status.get("configured") else []
    except Exception:
        card_status = {"enabled": False, "configured": False}
        card_items = []

    try:
        from core.trade_terminal import execution_enabled, execution_fee_bps
        execution_live = bool(execution_enabled())
        execution_fee = float(execution_fee_bps()) / 100.0
    except Exception:
        execution_live = False
        execution_fee = 0.0

    wc_enabled = bool(str(os.getenv("WALLETCONNECT_PROJECT_ID", "")).strip())
    bnb_binding = get_binding(uid)
    ton_binding = get_ton_binding(uid)

    points = _num(gamification.get("points", 0))
    referrals = int(referral.get("count", 0) or 0)
    bnb_label = "✅" if bnb_binding else "⚪"
    ton_label = "✅" if ton_binding else "⚪"
    bnb_deposit_label = "OPEN" if bnb_deposits_open() else "CLOSED"
    ton_deposit_label = "OPEN" if ton_deposits_open() else "CLOSED"
    commission = _num(referral.get("commission", 0))

    next_action = {
        "id": "rewards",
        "title": "פתח את מרכז הצמיחה",
        "reason": "בחר מסלול הכנסה, שימוש או תגמול.",
    }
    if open_tasks:
        next_action = {
            "id": "tasks",
            "title": "סיים משימה",
            "reason": f"{open_tasks} משימות פתוחות עם תגמול פוטנציאלי.",
        }
    elif referrals < 5:
        next_action = {
            "id": "referral",
            "title": "הזמן חבר",
            "reason": f"עוד {5 - referrals} הפניות עד אבן הדרך הקיימת של VIP.",
        }
    elif not bnb_binding:
        next_action = {
            "id": "bnb",
            "title": "חבר BNB",
            "reason": "WalletConnect או ארנק injected מאפשרים אימות בלי למסור מפתח פרטי.",
        }
    elif not ton_binding:
        next_action = {
            "id": "ton",
            "title": "חבר TON",
            "reason": "אימות TON פותח את שכבת הקבלה כשההפקדות פעילות.",
        }

    owner_revenue = None
    if has_permission(uid, "exec.audit"):
        try:
            owner_revenue = revenue_ledger.summary()
        except Exception:
            owner_revenue = None

    return {
        "generated_at": int(time.time()),
        "next_action": next_action,
        "wallet": {
            "credits": _num(wallet.get("credits", 0)),
            "staked": _num(wallet.get("staked", 0)),
            "slh": _num(wallet.get("live_token_balance", wallet.get("token_balance", 0))),
        },
        "rewards": {
            "points": points,
            "ledger_points": reward_totals["points"],
            "ledger_credits": reward_totals["credits"],
            "reward_events": reward_totals["entries"],
            "referrals": referrals,
            "referral_commission": commission,
            "tasks_open": open_tasks,
            "tasks_completed": completed_tasks,
            "tasks_total": completed_tasks + open_tasks,
            "academy_courses": academy["enrolled_courses"],
            "academy_lessons_completed": academy["completed_lessons"],
            "vip_active": vip_active,
        },
        "rails": [
            {
                "id": "stars",
                "title": "⭐ Stars / Digital",
                "status": "active" if stars_catalog else "empty",
                "detail": f"{len(stars_catalog)} מוצרים · Packs {pack_prices} · VIP {VIP_MONTHLY_STARS} Stars",
                "action": "market",
            },
            {
                "id": "card",
                "title": "💳 Card / Hardware",
                "status": "active" if card_status.get("enabled") and card_status.get("configured") else "staged",
                "detail": f"{len(card_items)} מוצרי חומרה מוגדרים" if card_items else "ממתין להגדרת PayPlus ומחירי מוצר",
                "action": "market",
            },
            {
                "id": "wallets",
                "title": "👛 BNB + TON",
                "status": "connected" if bnb_binding or ton_binding else "ready",
                "detail": (
                    f"BNB {"✅" if bnb_binding else "⚪"} · "
                    f"TON {"✅" if ton_binding else "⚪"} · "
                    f"BNB deposits {"OPEN" if bnb_deposits_open() else "CLOSED"} · "
                    f"TON native deposits {"OPEN" if ton_deposits_open() else "CLOSED"}"
                ),
                "action": "wallet",
            },
            {
                "id": "walletconnect",
                "title": "📱 WalletConnect",
                "status": "active" if wc_enabled else "staged",
                "detail": "BSC 56" if wc_enabled else "נדרשת הגדרת Project ID ציבורי",
                "action": "wallet",
            },
            {
                "id": "trade",
                "title": "📈 Trade",
                "status": "live" if execution_live else "safe_mode",
                "detail": ("Execution connector פעיל" if execution_live else "Scanner + planning פעילים; חתימה חיה עדיין סגורה") + f" · fee {execution_fee:.2f}%",
                "action": "trade",
            },
            {
                "id": "rewards",
                "title": "🎁 Reward Engine",
                "status": "active",
                "detail": "Tasks · Academy · Referral · Staking · Arcade (trusted events)",
                "action": "rewards",
            },
            {
                "id": "usdt_ton",
                "title": "💵 USDT on TON",
                "status": "staged",
                "detail": "דורש אימות Jetton master + receiving address + settlement לפני פתיחה",
                "action": "wallet",
            },
        ],
        "revenue": {
            "stars_catalog_items": len(stars_catalog),
            "card_catalog_items": len(card_items),
            "owner_confirmed_external": owner_revenue,
        },
    }