import time
import uuid
import state_manager


def _wallet(db, uid):
    user = db.setdefault("users", {}).setdefault(str(uid), {})
    return user.setdefault("wallet", {})


def _append_ledger(db, event):
    db.setdefault("ledger", []).append(event)


def _event(
    wallet,
    uid,
    type_,
    amount,
    reason,
    reference=None,
    idempotency_key=None,
):
    return {
        "event_id": str(uuid.uuid4()),
        "uid": str(uid),
        "type": type_,
        "amount": amount,
        "reason": reason,
        "reference": reference,
        "idempotency_key": idempotency_key,
        "timestamp": time.time(),
        "credits_before": wallet.get("credits", 0),
        "credits_after": wallet.get("credits", 0),
        "staked_before": wallet.get("staked", 0),
        "staked_after": wallet.get("staked", 0),
    }


def _already_processed(db, key):
    if not key:
        return False

    return any(
        e.get("idempotency_key") == key
        for e in db.get("ledger", [])
    )


def credit(
    uid,
    amount,
    reason,
    source="system",
    idempotency_key=None,
):
    if amount <= 0:
        raise ValueError("Amount must be positive")

    def mutate(db):
        wallet = _wallet(db, uid)

        if _already_processed(db, idempotency_key):
            return wallet["credits"]

        event = _event(
            wallet,
            uid,
            "credit",
            amount,
            reason,
            source,
            idempotency_key,
        )

        wallet["credits"] = wallet.get("credits", 0) + amount

        event["credits_after"] = wallet["credits"]
        event["staked_after"] = wallet.get("staked", 0)

        _append_ledger(db, event)

        return wallet["credits"]

    return state_manager.atomic_update(mutate)


def debit(
    uid,
    amount,
    reason,
    source="system",
    idempotency_key=None,
):
    if amount <= 0:
        raise ValueError("Amount must be positive")

    def mutate(db):
        wallet = _wallet(db, uid)

        if _already_processed(db, idempotency_key):
            return wallet["credits"]

        current = wallet.get("credits", 0)

        if current < amount:
            raise ValueError("Insufficient funds")

        event = _event(
            wallet,
            uid,
            "debit",
            -amount,
            reason,
            source,
            idempotency_key,
        )

        wallet["credits"] = current - amount

        event["credits_after"] = wallet["credits"]
        event["staked_after"] = wallet.get("staked", 0)

        _append_ledger(db, event)

        return wallet["credits"]

    return state_manager.atomic_update(mutate)


def stake(
    uid,
    amount,
    idempotency_key=None,
):
    if amount <= 0:
        raise ValueError("Amount must be positive")

    def mutate(db):
        wallet = _wallet(db, uid)

        if _already_processed(db, idempotency_key):
            return wallet.get("staked", 0)

        credits = wallet.get("credits", 0)

        if credits < amount:
            raise ValueError("Insufficient credits")

        event = _event(
            wallet,
            uid,
            "stake",
            -amount,
            "stake",
            "staking",
            idempotency_key,
        )

        wallet["credits"] = credits - amount
        wallet["staked"] = wallet.get("staked", 0) + amount

        event["credits_after"] = wallet["credits"]
        event["staked_after"] = wallet["staked"]

        _append_ledger(db, event)

        return wallet["staked"]

    return state_manager.atomic_update(mutate)


def unstake(
    uid,
    amount,
    idempotency_key=None,
):
    if amount <= 0:
        raise ValueError("Amount must be positive")

    def mutate(db):
        wallet = _wallet(db, uid)

        if _already_processed(db, idempotency_key):
            return wallet["credits"]

        staked = wallet.get("staked", 0)

        if staked < amount:
            raise ValueError("Insufficient staked")

        event = _event(
            wallet,
            uid,
            "unstake",
            amount,
            "unstake",
            "staking",
            idempotency_key,
        )

        wallet["staked"] = staked - amount
        wallet["credits"] = wallet.get("credits", 0) + amount

        event["credits_after"] = wallet["credits"]
        event["staked_after"] = wallet["staked"]

        _append_ledger(db, event)

        return wallet["credits"]

    return state_manager.atomic_update(mutate)
