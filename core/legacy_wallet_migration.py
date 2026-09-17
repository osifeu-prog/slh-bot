"""Non-custodial legacy BSC wallet migration registry.

This records a verified relationship between a Telegram user and an old SLH
wallet. It never takes custody of keys and never broadcasts token transfers.
The caller is responsible for proving wallet ownership before recording a
claim.
"""
import re

import state_manager


_EVM_ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def normalize_wallet(address):
    address = str(address).strip() if isinstance(address, str) else ""
    if not _EVM_ADDRESS_RE.fullmatch(address):
        raise ValueError("INVALID_WALLET_ADDRESS")
    return address


def record_legacy_claim(uid, wallet, observed_balance):
    """Record a verified legacy-wallet relationship atomically.

    ``observed_balance`` is informational only; this function never mints,
    credits, transfers, or otherwise changes a user's financial balance.
    """
    uid = str(uid)
    wallet = normalize_wallet(wallet)

    if not isinstance(observed_balance, (int, float)) or observed_balance < 0:
        raise ValueError("INVALID_OBSERVED_BALANCE")

    key = wallet.lower()

    def mutate(db):
        users = db.setdefault("users", {})
        if uid not in users:
            raise ValueError("USER_NOT_FOUND")

        migrations = db.setdefault("legacy_wallet_migrations", {})
        existing = migrations.get(key)

        if existing:
            if str(existing.get("uid")) == uid:
                return {**existing, "status": "duplicate"}
            raise ValueError("WALLET_ALREADY_MIGRATED")

        record = {
            "uid": uid,
            "wallet": wallet,
            "observed_balance": float(observed_balance),
            "status": "claimed",
        }
        migrations[key] = record
        users[uid].setdefault("wallet", {})["legacy_bnb_wallet"] = wallet
        return record

    return state_manager.atomic_update(mutate)
