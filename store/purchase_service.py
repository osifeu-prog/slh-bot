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

    grant_result = None

    if "grant" in item:
        grant_result = apply_grant(uid, item["grant"])

    ledger = load_ledger()

    ledger.append({
        "user_id": str(uid),
        "item": item_id,
        "amount": price,
        "grant": grant_result,
        "timestamp": datetime.utcnow().isoformat()
    })

    save_ledger(ledger)

    return True, {
        "item": item["name"],
        "paid": price,
        "grant": grant_result
    }
