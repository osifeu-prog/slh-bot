import json
from pathlib import Path
from datetime import datetime, timezone

import state_manager

DB_PATH = Path("state/db.json")
LEDGER_PATH = Path("state/ledger.json")


def get_balance_safe(uid):
    db = state_manager.load_db()
    uid = str(uid)

    user = db.get("users", {}).get(uid)
    if not user:
        raise Exception("USER_NOT_FOUND")

    return user.get("wallet", {}).get("credits", 0)


def record_transaction(uid, amount, reason="unknown", meta=None):
    """
    SINGLE MONEY AUTHORITY.

    Every credit mutation:
        load -> validate -> mutate -> ledger -> atomic save

    No caller should modify wallet["credits"] directly.
    """
    uid = str(uid)

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    if not reason:
        raise ValueError("reason is required")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        wallet = users[uid].setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + amount

        if after < 0:
            raise ValueError("INSUFFICIENT_CREDITS")

        wallet["credits"] = after

        ledger = []
        if LEDGER_PATH.exists():
            try:
                ledger = json.loads(
                    LEDGER_PATH.read_text(encoding="utf-8")
                )
            except Exception:
                ledger = []

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": amount,
            "after": after,
            "reason": reason,
            "meta": meta
        })

        LEDGER_PATH.write_text(
            json.dumps(
                ledger,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return after

    return state_manager.atomic_update(mutate)
