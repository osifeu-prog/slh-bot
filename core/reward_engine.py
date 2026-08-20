"""
SLH Reward Engine
Single reward gateway
"""

from datetime import datetime
from core import economy_bridge
from core import profile_manager
import json
from pathlib import Path


LEDGER = Path("state/rewards_ledger.json")


def _load():
    if not LEDGER.exists():
        return []

    try:
        return json.loads(
            LEDGER.read_text(
                encoding="utf-8"
            )
        )
    except:
        return []


def _save(data):
    LEDGER.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def grant(
    uid,
    reason,
    credits=0,
    points=0
):

    if not uid:
        raise ValueError("Reward requires user id")

    if not reason:
        raise ValueError("Reward requires reason")

    if credits == 0 and points == 0:
        raise ValueError("Empty reward rejected")

    result={}

    if credits:
        result["credits"] = economy_bridge.add_credits(
            uid,
            credits
        )

    if points:
        profile_manager.add_points(
            uid,
            points
        )

        result["points"] = points


    entry={
        "user":str(uid),
        "reason":reason,
        "credits":credits,
        "points":points,
        "timestamp":datetime.utcnow().isoformat()
    }


    ledger=_load()
    ledger.append(entry)
    _save(ledger)


    return result
