import json
from datetime import datetime

from store.engine import load_items
from core.economy_bridge import get_balance, spend
from store.grant_engine import apply_grant


LEDGER_FILE = "state/rewards_ledger.json"


def load_ledger():
    try:
        return json.load(open(LEDGER_FILE, encoding="utf-8-sig"))
    except:
        return []


def save_ledger(data):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def purchase(uid, item_id):

    items = load_items()

    if item_id not in items:
        return False, "ITEM_NOT_FOUND"

    item = items[item_id]
    price = item.get("price", 0)

    balance = get_balance(uid)

    if balance < price:
        return False, "NOT_ENOUGH_SLH"

    result = spend(uid, price)

    if result is False:
        return False, "PAYMENT_FAILED"

    # --- Referral commission ---
    commission = 0
    try:
        import state_manager
        db = state_manager.load_db()
        users = db.get("users", {})
        referrer_uid = users.get(str(uid), {}).get("referral", {}).get("referred_by")
        if referrer_uid and str(referrer_uid) != str(uid):
            referrer_uid = str(referrer_uid)
            if referrer_uid in users:
                commission = round(price * 0.85, 2)
                if commission > 0:
                    from core.economy_bridge import add_credits
                    add_credits(
                        referrer_uid,
                        commission,
                        reason="referral:commission",
                        meta={"source_uid": str(uid), "purchase_item": item_id}
                    )
    except Exception:
        commission = 0
    # -----------------------------

    grant_result = None

    if "grant" in item:
        grant_result = apply_grant(uid, item["grant"])

    ledger = load_ledger()

    ledger.append({
        "user_id": str(uid),
        "item": item_id,
        "amount": price,
        "grant": grant_result,
        "commission": commission,
        "timestamp": datetime.utcnow().isoformat()
    })

    save_ledger(ledger)

    return True, {
        "item": item["name"],
        "paid": price,
        "grant": grant_result,
        "commission": commission
    }
