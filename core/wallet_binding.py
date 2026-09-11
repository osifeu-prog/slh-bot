"""Authenticated Telegram -> EVM wallet ownership binding.

This module is deliberately separate from deposit crediting. A verified binding
only establishes ownership; deposit_monitor/economy_service remain the
financial authorities.
"""
from datetime import datetime, timezone, timedelta
import secrets

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

import state_manager

CHAIN = "bsc"
CHALLENGE_TTL_SECONDS = 300


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _parse_iso(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def normalize_address(address):
    if not isinstance(address, str) or not Web3.is_address(address.strip()):
        raise ValueError("INVALID_WALLET_ADDRESS")
    return Web3.to_checksum_address(address.strip())


def challenge_message(uid, address, nonce):
    return (
        "SLH OS BNB wallet ownership verification\n"
        f"Telegram account: {uid}\n"
        f"Wallet: {address}\n"
        f"Nonce: {nonce}\n"
        "This signature proves control of this wallet. It does not authorize a transaction."
    )


def issue_challenge(uid, address):
    uid = str(uid)
    address = normalize_address(address)
    nonce = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(seconds=CHALLENGE_TTL_SECONDS)
    message = challenge_message(uid, address, nonce)

    def mutate(db):
        challenges = db.setdefault("wallet_challenges", {})
        challenges[f"{CHAIN}:{uid}"] = {
            "uid": uid,
            "chain": CHAIN,
            "address": address,
            "nonce": nonce,
            "message": message,
            "created_at": _iso(_now()),
            "expires_at": _iso(expires_at),
            "consumed": False,
        }

    state_manager.atomic_update(mutate)
    return {"chain": CHAIN, "address": address, "message": message, "expires_at": _iso(expires_at)}


def _signature_bytes(signature):
    raw = str(signature).strip()
    if raw.startswith(("0x", "0X")):
        raw = raw[2:]
    try:
        value = bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError("INVALID_SIGNATURE") from exc
    if len(value) != 65:
        raise ValueError("INVALID_SIGNATURE")
    return value


def verify_signature(uid, address, signature):
    uid = str(uid)
    address = normalize_address(address)
    if not isinstance(signature, str) or not signature.strip():
        raise ValueError("INVALID_SIGNATURE")

    key = f"{CHAIN}:{uid}"

    def mutate(db):
        challenges = db.setdefault("wallet_challenges", {})
        challenge = challenges.get(key)
        if not challenge or challenge.get("consumed"):
            raise ValueError("CHALLENGE_NOT_FOUND")
        if challenge.get("address", "").lower() != address.lower():
            raise ValueError("CHALLENGE_ADDRESS_MISMATCH")
        if _now() >= _parse_iso(challenge["expires_at"]):
            raise ValueError("CHALLENGE_EXPIRED")

        message = challenge["message"]
        try:
            recovered = Account.recover_message(
                encode_defunct(text=message),
                signature=_signature_bytes(signature),
            )
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("INVALID_SIGNATURE") from exc

        if recovered.lower() != address.lower():
            raise ValueError("WALLET_OWNERSHIP_NOT_PROVEN")

        bindings = db.setdefault("wallet_bindings", {})
        address_key = address.lower()
        existing = bindings.get(address_key)
        if existing and str(existing.get("uid")) != uid:
            raise ValueError("WALLET_ALREADY_BOUND")

        # One Telegram account has at most one verified BNB wallet.
        for bound_address, binding in bindings.items():
            if str(binding.get("uid")) == uid and bound_address != address_key:
                raise ValueError("USER_ALREADY_HAS_BNB_WALLET")

        bindings[address_key] = {
            "uid": uid,
            "chain": CHAIN,
            "address": address,
            "verified_at": _iso(_now()),
        }
        challenge["consumed"] = True
        challenge["consumed_at"] = _iso(_now())
        return bindings[address_key]

    return state_manager.atomic_update(mutate)


def get_binding(uid):
    uid = str(uid)
    db = state_manager.load_db()
    for binding in db.get("wallet_bindings", {}).values():
        if str(binding.get("uid")) == uid and binding.get("chain") == CHAIN:
            return binding
    return None
