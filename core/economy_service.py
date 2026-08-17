import json
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path("state/db.json")
LEDGER_PATH = Path("state/ledger.json")


def _load():
    return json.loads(
        DB_PATH.read_text(encoding="utf-8")
    )


def _save(data):
    DB_PATH.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def get_balance_safe(uid):

    db = _load()

    user = db.get("users",{}).get(str(uid))

    if not user:
        raise Exception("USER_NOT_FOUND")

    return user.get(
        "wallet",
        {}
    ).get(
        "credits",
        0
    )


def record_transaction(
    uid,
    amount,
    reason="unknown",
    meta=None
):

    db = _load()

    uid=str(uid)

    if uid not in db.get("users",{}):
        raise Exception("USER_NOT_FOUND")

    wallet = db["users"][uid].setdefault(
        "wallet",
        {}
    )

    before = wallet.get(
        "credits",
        0
    )

    after = before + amount

    wallet["credits"] = after


    ledger=[]

    if LEDGER_PATH.exists():
        ledger=json.loads(
            LEDGER_PATH.read_text(
                encoding="utf-8"
            )
        )


    ledger.append({

        "time":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "uid":uid,

        "before":before,

        "amount":amount,

        "after":after,

        "reason":reason,

        "meta":meta or {}

    })


    LEDGER_PATH.write_text(
        json.dumps(
            ledger,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    _save(db)


    return after
