"""Canonical TON wallet ownership binding using TON Connect ton_proof.

This module establishes wallet ownership only. It never credits Credits or sends
TON. Deposit settlement is handled by core.ton_deposit_service.

The verification follows the TON Connect ton_proof v2 construction:
ton-proof-item-v2/ + address + domain + timestamp + payload, hashed and wrapped
with the ton-connect prefix before Ed25519 verification.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import struct
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import state_manager


CHAIN = "ton"
MAINNET = "-239"
CHALLENGE_TTL_SECONDS = 900
PROOF_TTL_SECONDS = 900
PROOF_FUTURE_SKEW_SECONDS = 60
TONCENTER_URL = os.getenv("TONCENTER_URL", "https://toncenter.com/api/v2").rstrip("/")
TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY", "").strip()
TON_PROOF_DOMAIN = os.getenv("TON_PROOF_DOMAIN", "slh-nft.com").strip().lower()
TON_PROOF_ALLOWED_DOMAINS = {
    x.strip().lower()
    for x in os.getenv(
        "TON_PROOF_ALLOWED_DOMAINS",
        "slh-nft.com,slh.co.il,web-production-22f28.up.railway.app",
    ).split(",")
    if x.strip()
}
TON_PROOF_ALLOWED_DOMAINS.add(TON_PROOF_DOMAIN)
TONAPI_URL = os.getenv("TONAPI_URL", "https://tonapi.io").rstrip("/")
TONAPI_TOKEN = os.getenv("TONAPI_TOKEN", "").strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _normalize_domain(domain: str | None) -> str:
    value = str(domain or "").strip().lower()
    if "://" in value:
        parsed = urlparse(value)
        value = (parsed.hostname or "").lower()
    value = value.rstrip(".")
    if not value or value not in TON_PROOF_ALLOWED_DOMAINS:
        raise ValueError("TON_PROOF_DOMAIN_NOT_ALLOWED")
    if "." not in value:
        raise ValueError("TON_PROOF_DOMAIN_INVALID")
    return value


def _decode_b64(value: str) -> bytes:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("INVALID_TON_PROOF")
    padded = raw + "=" * (-len(raw) % 4)
    try:
        return base64.b64decode(padded, validate=False)
    except Exception:
        try:
            return base64.urlsafe_b64decode(padded)
        except Exception as exc:
            raise ValueError("INVALID_TON_PROOF") from exc


def _crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc


def normalize_ton_address(address: str) -> str:
    if not isinstance(address, str):
        raise ValueError("INVALID_TON_ADDRESS")
    value = address.strip()
    if ":" in value:
        workchain, addr_hex = value.split(":", 1)
        try:
            wc = int(workchain)
        except ValueError as exc:
            raise ValueError("INVALID_TON_ADDRESS") from exc
        if wc < -(2**31) or wc > (2**31 - 1):
            raise ValueError("INVALID_TON_ADDRESS")
        if len(addr_hex) != 64:
            raise ValueError("INVALID_TON_ADDRESS")
        try:
            bytes.fromhex(addr_hex)
        except ValueError as exc:
            raise ValueError("INVALID_TON_ADDRESS") from exc
        return f"{wc}:{addr_hex.lower()}"

    raw = value.replace("-", "+").replace("_", "/")
    padded = raw + "=" * (-len(raw) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True)
    except Exception as exc:
        raise ValueError("INVALID_TON_ADDRESS") from exc

    if len(decoded) != 36:
        raise ValueError("INVALID_TON_ADDRESS")

    payload, crc = decoded[:34], decoded[34:]
    if int.from_bytes(crc, "big") != _crc16(payload):
        raise ValueError("INVALID_TON_ADDRESS")

    _tag = payload[0]
    workchain = int.from_bytes(payload[1:2], "big", signed=True)
    account = payload[2:]
    return f"{workchain}:{account.hex()}"


def address_bytes(address: str) -> bytes:
    raw = normalize_ton_address(address)
    workchain, addr_hex = raw.split(":", 1)
    return struct.pack(">i", int(workchain)) + bytes.fromhex(addr_hex)


def issue_ton_challenge(uid, domain: str | None = None, ttl_seconds: int = CHALLENGE_TTL_SECONDS):
    uid = str(uid)
    domain = _normalize_domain(domain or TON_PROOF_DOMAIN)
    if ttl_seconds <= 0 or ttl_seconds > 900:
        raise ValueError("INVALID_CHALLENGE_TTL")

    payload = "slh-ton-" + secrets.token_urlsafe(32)
    sign_data_message = "SLH OS wallet verification\\nChallenge: " + payload
    expires_at = _now() + timedelta(seconds=ttl_seconds)

    def mutate(db):
        challenges = db.setdefault("ton_wallet_challenges", {})
        challenges[uid] = {
            "uid": uid,
            "chain": CHAIN,
            "payload": payload,
            "sign_data_message": sign_data_message,
            "domain": domain,
            "created_at": _iso(_now()),
            "expires_at": _iso(expires_at),
            "consumed": False,
        }

    state_manager.atomic_update(mutate)
    return {
        "chain": CHAIN,
        "network": MAINNET,
        "payload": payload,
        "sign_data_message": sign_data_message,
        "domain": domain,
        "expires_at": _iso(expires_at),
    }


def _proof_digest(raw_address: str, domain: str, timestamp: int, payload: str) -> bytes:
    domain_bytes = domain.encode("utf-8")
    message = (
        b"ton-proof-item-v2/"
        + address_bytes(raw_address)
        + struct.pack("<I", len(domain_bytes))
        + domain_bytes
        + struct.pack("<Q", int(timestamp))
        + payload.encode("utf-8")
    )
    message_hash = hashlib.sha256(message).digest()
    return hashlib.sha256(b"\xff\xffton-connect" + message_hash).digest()


def _public_key_from_stack_value(value) -> str:
    if isinstance(value, int):
        number = value
    else:
        text = str(value or "").strip()
        if text.lower().startswith("0x"):
            number = int(text, 16)
        elif text.isdigit():
            number = int(text, 10)
        else:
            number = int(text, 16)
    if number < 0 or number >= 2**256:
        raise ValueError("TON_PUBLIC_KEY_INVALID")
    return number.to_bytes(32, "big").hex()


def _get_state_init_info(wallet_state_init: str) -> dict:
    value = str(wallet_state_init or "").strip()
    if not value:
        raise ValueError("TON_STATE_INIT_REQUIRED")

    headers = {"Authorization": f"Bearer {TONAPI_TOKEN}"} if TONAPI_TOKEN else {}
    try:
        response = requests.post(
            f"{TONAPI_URL}/v2/tonconnect/stateinit",
            json={"state_init": value},
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise ValueError("TON_STATE_INIT_LOOKUP_FAILED") from exc

    if not isinstance(data, dict):
        raise ValueError("TON_STATE_INIT_INVALID")

    address = str(data.get("address") or "").strip()
    public_key = str(data.get("public_key") or "").strip().lower().removeprefix("0x")
    if not address or len(public_key) != 64:
        raise ValueError("TON_STATE_INIT_INVALID")

    return {"address": normalize_ton_address(address), "public_key": _decode_public_key(public_key)}


def _get_onchain_public_key(address: str) -> str:
    url = f"{TONCENTER_URL}/runGetMethod"
    headers = {"X-API-Key": TONCENTER_API_KEY} if TONCENTER_API_KEY else {}
    response = requests.post(
        url,
        json={"address": address, "method": "get_public_key", "stack": []},
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok", True):
        raise ValueError("TON_PUBLIC_KEY_LOOKUP_FAILED")

    result = data.get("result") or {}
    stack = result.get("stack") or []
    if not stack:
        raise ValueError("TON_PUBLIC_KEY_UNAVAILABLE")

    item = stack[0]
    if isinstance(item, dict):
        value = item.get("value")
    elif isinstance(item, (list, tuple)) and len(item) >= 2:
        value = item[1]
    else:
        value = item
    return _public_key_from_stack_value(value)


def _decode_public_key(value: str) -> bytes:
    raw = str(value or "").strip().lower().removeprefix("0x")
    if len(raw) != 64:
        raise ValueError("TON_PUBLIC_KEY_INVALID")
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError("TON_PUBLIC_KEY_INVALID") from exc


def _sign_data_digest(raw_address: str, domain: str, timestamp: int, text: str) -> bytes:
    domain_bytes = domain.encode("utf-8")
    data_bytes = text.encode("utf-8")
    message = (
        b"\\xff\\xff"
        + b"ton-connect/sign-data/"
        + address_bytes(raw_address)
        + struct.pack(">I", len(domain_bytes))
        + domain_bytes
        + struct.pack(">Q", int(timestamp))
        + b"txt"
        + struct.pack(">I", len(data_bytes))
        + data_bytes
    )
    return hashlib.sha256(message).digest()


def verify_ton_sign_data(uid, sign_payload: dict):
    uid = str(uid)
    if not isinstance(sign_payload, dict):
        raise ValueError("INVALID_TON_SIGN_DATA")

    address = sign_payload.get("address")
    raw_address = normalize_ton_address(address)

    network = str(sign_payload.get("network", "")).strip()
    if network and network != MAINNET:
        raise ValueError("TON_NETWORK_NOT_SUPPORTED")

    wallet_state_init = str(sign_payload.get("wallet_state_init") or "").strip()
    if not wallet_state_init:
        raise ValueError("TON_STATE_INIT_REQUIRED")

    state_info = _get_state_init_info(wallet_state_init)
    if state_info["address"] != raw_address:
        raise ValueError("TON_STATE_INIT_ADDRESS_MISMATCH")

    public_key = state_info["public_key"]
    supplied_public_key = sign_payload.get("public_key")
    if supplied_public_key and _decode_public_key(supplied_public_key) != public_key:
        raise ValueError("TON_PUBLIC_KEY_MISMATCH")

    try:
        timestamp = int(sign_payload.get("timestamp"))
        domain = _normalize_domain(sign_payload.get("domain"))
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_TON_SIGN_DATA") from exc

    now_ts = int(_now().timestamp())
    if timestamp > now_ts + PROOF_FUTURE_SKEW_SECONDS:
        raise ValueError("TON_PROOF_TIMESTAMP_INVALID")
    if timestamp < now_ts - PROOF_TTL_SECONDS:
        raise ValueError("TON_PROOF_EXPIRED")

    payload = sign_payload.get("payload") or {}
    if not isinstance(payload, dict) or payload.get("type") != "text":
        raise ValueError("TON_SIGN_DATA_TYPE_UNSUPPORTED")
    text_value = str(payload.get("text") or "")

    signature = _decode_b64(sign_payload.get("signature"))
    if len(signature) != 64:
        raise ValueError("INVALID_TON_SIGN_DATA")

    db = state_manager.load_db()
    challenge = (db.get("ton_wallet_challenges") or {}).get(uid)
    if not challenge:
        raise ValueError("TON_CHALLENGE_NOT_FOUND")
    if challenge.get("consumed"):
        raise ValueError("TON_CHALLENGE_CONSUMED")
    if _now() >= _parse_iso(challenge["expires_at"]):
        raise ValueError("TON_CHALLENGE_EXPIRED")

    expected_message = str(
        challenge.get("sign_data_message")
        or ("SLH OS wallet verification\\nChallenge: " + str(challenge.get("payload") or ""))
    )
    if text_value != expected_message:
        raise ValueError("TON_CHALLENGE_MISMATCH")
    if str(challenge.get("domain", "")).lower() != domain:
        raise ValueError("TON_PROOF_DOMAIN_MISMATCH")

    digest = _sign_data_digest(raw_address, domain, timestamp, text_value)
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, digest)
    except Exception as exc:
        raise ValueError("INVALID_TON_SIGN_DATA") from exc

    def mutate(db):
        challenges = db.setdefault("ton_wallet_challenges", {})
        current = challenges.get(uid)
        if not current or current.get("consumed"):
            raise ValueError("TON_CHALLENGE_CONSUMED")
        if current.get("payload") != challenge.get("payload"):
            raise ValueError("TON_CHALLENGE_MISMATCH")

        bindings = db.setdefault("ton_wallet_bindings", {})
        existing = bindings.get(raw_address)
        if existing and str(existing.get("uid")) != uid:
            raise ValueError("TON_WALLET_ALREADY_BOUND")

        for bound_address, binding in bindings.items():
            if str(binding.get("uid")) == uid and bound_address != raw_address:
                raise ValueError("USER_ALREADY_HAS_TON_WALLET")

        binding = {
            "uid": uid,
            "chain": CHAIN,
            "network": MAINNET,
            "address": address,
            "address_raw": raw_address,
            "public_key": public_key.hex(),
            "domain": domain,
            "verified_at": _iso(_now()),
            "proof_timestamp": timestamp,
            "verification_method": "ton_sign_data",
        }
        bindings[raw_address] = binding
        current["consumed"] = True
        current["consumed_at"] = _iso(_now())
        current["verification_method"] = "ton_sign_data"
        return binding

    return state_manager.atomic_update(mutate)


def verify_ton_proof(uid, proof_payload: dict):
    uid = str(uid)
    if not isinstance(proof_payload, dict):
        raise ValueError("INVALID_TON_PROOF")

    supplied_address = proof_payload.get("address")
    raw_address = normalize_ton_address(supplied_address)

    network = str(proof_payload.get("network", "")).strip()
    if network != MAINNET:
        raise ValueError("TON_NETWORK_NOT_SUPPORTED")

    supplied_public_key = proof_payload.get("public_key")
    public_key = _decode_public_key(supplied_public_key) if supplied_public_key else None
    wallet_state_init = str(proof_payload.get("wallet_state_init") or "").strip()
    if not wallet_state_init:
        raise ValueError("TON_STATE_INIT_REQUIRED")
    state_info = _get_state_init_info(wallet_state_init)
    if state_info["address"] != raw_address:
        raise ValueError("TON_STATE_INIT_ADDRESS_MISMATCH")
    state_public_key = state_info["public_key"]
    if public_key is not None and public_key != state_public_key:
        raise ValueError("TON_PUBLIC_KEY_MISMATCH")
    public_key = state_public_key
    proof = proof_payload.get("proof") or {}
    if proof.get("payload") is None:
        raise ValueError("INVALID_TON_PROOF")

    try:
        timestamp = int(proof.get("timestamp"))
        domain = _normalize_domain((proof.get("domain") or {}).get("value"))
        length_bytes = int((proof.get("domain") or {}).get("lengthBytes"))
    except (TypeError, ValueError):
        raise ValueError("INVALID_TON_PROOF")

    domain_bytes = domain.encode("utf-8")
    if length_bytes != len(domain_bytes):
        raise ValueError("INVALID_TON_PROOF")

    now_ts = int(_now().timestamp())
    if timestamp > now_ts + PROOF_FUTURE_SKEW_SECONDS:
        raise ValueError("TON_PROOF_TIMESTAMP_INVALID")
    if timestamp < now_ts - PROOF_TTL_SECONDS:
        raise ValueError("TON_PROOF_EXPIRED")

    signature = _decode_b64(proof.get("signature"))
    if len(signature) != 64:
        raise ValueError("INVALID_TON_PROOF")

    db = state_manager.load_db()
    challenge = (db.get("ton_wallet_challenges") or {}).get(uid)
    if not challenge:
        raise ValueError("TON_CHALLENGE_NOT_FOUND")
    if challenge.get("consumed"):
        raise ValueError("TON_CHALLENGE_CONSUMED")
    if _now() >= _parse_iso(challenge["expires_at"]):
        raise ValueError("TON_CHALLENGE_EXPIRED")
    if str(challenge.get("payload")) != str(proof.get("payload")):
        raise ValueError("TON_CHALLENGE_MISMATCH")
    if str(challenge.get("domain", "")).lower() != domain:
        raise ValueError("TON_PROOF_DOMAIN_MISMATCH")

    digest = _proof_digest(raw_address, domain, timestamp, str(proof.get("payload")))
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, digest)
    except Exception as exc:
        raise ValueError("INVALID_TON_PROOF") from exc

    def mutate(db):
        challenges = db.setdefault("ton_wallet_challenges", {})
        current = challenges.get(uid)
        if not current or current.get("consumed"):
            raise ValueError("TON_CHALLENGE_CONSUMED")
        if current.get("payload") != proof.get("payload"):
            raise ValueError("TON_CHALLENGE_MISMATCH")

        bindings = db.setdefault("ton_wallet_bindings", {})
        existing = bindings.get(raw_address)
        if existing and str(existing.get("uid")) != uid:
            raise ValueError("TON_WALLET_ALREADY_BOUND")

        for bound_address, binding in bindings.items():
            if str(binding.get("uid")) == uid and bound_address != raw_address:
                raise ValueError("USER_ALREADY_HAS_TON_WALLET")

        binding = {
            "uid": uid,
            "chain": CHAIN,
            "network": MAINNET,
            "address": supplied_address,
            "address_raw": raw_address,
            "public_key": public_key.hex(),
            "domain": domain,
            "verified_at": _iso(_now()),
            "proof_timestamp": timestamp,
        }
        bindings[raw_address] = binding
        current["consumed"] = True
        current["consumed_at"] = _iso(_now())
        return binding

    return state_manager.atomic_update(mutate)


def get_ton_binding(uid):
    uid = str(uid)
    db = state_manager.load_db()
    for binding in (db.get("ton_wallet_bindings") or {}).values():
        if str(binding.get("uid")) == uid and binding.get("chain") == CHAIN:
            return binding
    return None
