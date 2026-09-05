"""Read-only reconciliation audit for SLH money state.

Usage:
    python tools/money_reconciliation.py

This script never mutates state/db.json.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH = Path("state/db.json")


def main():
    if not DB_PATH.exists():
        raise SystemExit("STATE_DB_MISSING")

    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    users = db.get("users", {})
    transactions = db.get("transactions", [])
    ledger = db.get("ledger", [])
    claimed = db.get("claimed_deposits", {})
    used_ton = db.get("used_ton_txs", [])

    bnb_txs = [t for t in transactions if t.get("type") == "bnb"]
    ton_txs = [t for t in transactions if t.get("type") == "ton"]
    bnb_ledger = [e for e in ledger if e.get("reason") == "claim:bnb_deposit"]
    ton_ledger = [e for e in ledger if e.get("reason") == "ton:deposit"]

    bnb_hashes = [str(t.get("tx_hash", "")) for t in bnb_txs if t.get("tx_hash")]
    ton_hashes = [str(t.get("tx_hash", "")) for t in ton_txs if t.get("tx_hash")]
    claimed_hashes = [str(k) for k in claimed]

    print("=== SLH MONEY RECONCILIATION (READ ONLY) ===")
    print(f"users={len(users)}")
    print(f"transactions={len(transactions)}")
    print(f"ledger={len(ledger)}")
    print(f"claimed_deposits={len(claimed)}")
    print(f"used_ton_txs={len(used_ton)}")
    print(f"bnb_transactions={len(bnb_txs)}")
    print(f"bnb_claim_ledger={len(bnb_ledger)}")
    print(f"ton_transactions={len(ton_txs)}")
    print(f"ton_deposit_ledger={len(ton_ledger)}")

    duplicate_bnb = sorted(h for h, n in Counter(bnb_hashes).items() if n > 1)
    duplicate_ton = sorted(h for h, n in Counter(ton_hashes).items() if n > 1)
    duplicate_used_ton = sorted(h for h, n in Counter(map(str, used_ton)).items() if n > 1)

    print(f"duplicate_bnb_tx_hashes={duplicate_bnb}")
    print(f"duplicate_ton_tx_hashes={duplicate_ton}")
    print(f"duplicate_used_ton_hashes={duplicate_used_ton}")

    bnb_ledger_hashes = {
        str(e.get("meta", {}).get("tx_hash"))
        for e in bnb_ledger
        if e.get("meta", {}).get("tx_hash")
    }
    claimed_set = set(claimed_hashes)
    bnb_set = set(bnb_hashes)

    print(f"bnb_missing_claim_record={sorted(bnb_set - claimed_set)}")
    print(f"bnb_missing_transaction={sorted(claimed_set - bnb_set)}")
    print(f"bnb_missing_ledger={sorted(bnb_set - bnb_ledger_hashes)}")

    # TON must have one transaction record and one used-tx marker per credited hash.
    used_ton_set = {str(x) for x in used_ton}
    print(f"ton_missing_used_marker={sorted(set(ton_hashes) - used_ton_set)}")
    print(f"ton_orphan_used_marker={sorted(used_ton_set - set(ton_hashes))}")

    # Wallet conservation check: ledger deltas must sum to the observed credit balance
    # only for users whose ledger contains complete history. Report, don't mutate.
    ledger_delta = defaultdict(float)
    for entry in ledger:
        uid = str(entry.get("uid"))
        try:
            ledger_delta[uid] += float(entry.get("amount", 0))
        except (TypeError, ValueError):
            print(f"invalid_ledger_amount uid={uid}")

    print("=== WALLET / LEDGER DELTA CHECK ===")
    for uid, user in sorted(users.items(), key=lambda x: str(x[0])):
        wallet = user.get("wallet", {})
        credits = float(wallet.get("credits", 0))
        staked = float(wallet.get("staked", 0))
        print(
            f"uid={uid} credits={credits:g} staked={staked:g} "
            f"ledger_delta={ledger_delta[str(uid)]:g}"
        )

    print("=== END ===")


if __name__ == "__main__":
    main()
