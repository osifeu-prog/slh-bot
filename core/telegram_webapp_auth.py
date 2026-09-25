"""Server-side authentication for Telegram Mini App initData."""

import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


DEFAULT_MAX_AGE = 3600
TELEGRAM_ED25519_PUBLIC_KEY_HEX = (
    "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d"
)


def _bot_token():
    token = str(os.getenv("BOT_TOKEN", "")).strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN_MISSING")
    return token


def _hmac_hex(secret_key, message):
    return hmac.new(secret_key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def _safe_hmac_diagnostics(init_data, data, received_hash, secret_key):
    """Identify matching canonicalizations without changing authentication behavior."""
    decoded_all = "\n".join(
        f"{key}={value}"
        for key, value in sorted(data.items())
    )
    decoded_without_signature = "\n".join(
        f"{key}={value}"
        for key, value in sorted(data.items())
        if key != "signature"
    )

    raw_pairs = [
        part for part in init_data.split("&")
        if part and not part.startswith("hash=")
    ]
    raw_all = "\n".join(sorted(raw_pairs))
    raw_without_signature = "\n".join(
        sorted(
            part for part in raw_pairs
            if not part.startswith("signature=")
        )
    )

    candidates = {
        "decoded_all": _hmac_hex(secret_key, decoded_all),
        "decoded_no_signature": _hmac_hex(secret_key, decoded_without_signature),
        "raw_all": _hmac_hex(secret_key, raw_all),
        "raw_no_signature": _hmac_hex(secret_key, raw_without_signature),
    }

    legacy_key = hashlib.sha256(_bot_token().encode("utf-8")).digest()
    candidates["legacy_sha256_token"] = _hmac_hex(legacy_key, decoded_all)

    return {
        "keys": sorted(data),
        "hash_len": len(received_hash),
        "signature_present": "signature" in data,
        "matches": sorted(
            name for name, digest in candidates.items()
            if hmac.compare_digest(received_hash.lower(), digest)
        ),
    }


def _verify_ed25519_signature(data):
    """Verify Telegram's official third-party initData signature."""
    signature = str(data.get("signature", "") or "")
    if not signature:
        return False

    token = _bot_token()
    bot_id = token.split(":", 1)[0]
    if not bot_id.isdigit():
        return False

    check_string = "\n".join(
        [
            f"{bot_id}:WebAppData",
            *(
                f"{key}={value}"
                for key, value in sorted(data.items())
                if key not in {"hash", "signature"}
            ),
        ]
    )

    try:
        padded = signature + ("=" * (-len(signature) % 4))
        signature_bytes = base64.urlsafe_b64decode(padded.encode("ascii"))
        public_key = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(TELEGRAM_ED25519_PUBLIC_KEY_HEX)
        )
        public_key.verify(signature_bytes, check_string.encode("utf-8"))
        return True
    except (ValueError, TypeError, UnicodeEncodeError):
        return False


def validate_init_data(init_data, max_age=DEFAULT_MAX_AGE, now=None):
    """Validate Telegram WebApp initData and return the authenticated user."""
    if not isinstance(init_data, str) or not init_data.strip():
        raise ValueError("TELEGRAM_INIT_DATA_MISSING")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("TELEGRAM_INIT_DATA_DUPLICATE_KEY")
        data[key] = value

    received_hash = data.pop("hash", "")
    if not received_hash:
        raise ValueError("TELEGRAM_INIT_DATA_HASH_MISSING")

    check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(data.items())
    )
    secret_key = hmac.new(
        _bot_token().encode("utf-8"),
        b"WebAppData",
        hashlib.sha256,
    ).digest()
    expected_hash = _hmac_hex(secret_key, check_string)

    if not hmac.compare_digest(received_hash.lower(), expected_hash):
        if not _verify_ed25519_signature(data):
            diag = _safe_hmac_diagnostics(init_data, data, received_hash, secret_key)
            detail = "TELEGRAM_INIT_DATA_INVALID"
            if diag["matches"]:
                detail += ";HMAC_DIAGNOSTIC=" + ",".join(diag["matches"])
            else:
                detail += (
                    ";HMAC_DIAGNOSTIC=NONE"
                    f";keys={','.join(diag['keys'])}"
                    f";hash_len={diag['hash_len']}"
                    f";signature_present={str(diag['signature_present']).lower()}"
                    ";ED25519=INVALID"
                )
            raise ValueError(detail)

    try:
        auth_date = int(data.get("auth_date", "0"))
    except (TypeError, ValueError):
        raise ValueError("TELEGRAM_INIT_DATA_AUTH_DATE_INVALID")

    current_time = int(time.time() if now is None else now)
    if auth_date <= 0 or auth_date > current_time + 60:
        raise ValueError("TELEGRAM_INIT_DATA_AUTH_DATE_INVALID")
    if current_time - auth_date > int(max_age):
        raise ValueError("TELEGRAM_INIT_DATA_EXPIRED")

    try:
        user = json.loads(data.get("user", "{}"))
    except json.JSONDecodeError:
        raise ValueError("TELEGRAM_INIT_DATA_USER_INVALID")

    uid = user.get("id")
    if uid is None:
        raise ValueError("TELEGRAM_INIT_DATA_USER_MISSING")

    return {"uid": str(uid), "user": user, "auth_date": auth_date}
