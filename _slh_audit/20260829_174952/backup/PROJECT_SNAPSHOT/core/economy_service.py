import json
from pathlib import Path
from datetime import datetime, timezone
import state_manager

DB_PATH = Path("state/db.json")




def get_balance_safe(uid):
    db = state_manager.load_db()
    uid = str(uid)

    user = db.get("users", {}).get(uid)

    if not user:
        raise Exception("USER_NOT_FOUND")

    return user.get("wallet", {}).get("credits", 0)


def record_transaction(uid, amount, reason="unknown", meta=None):
    uid = str(uid)

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + amount

        if after < 0:
            raise ValueError("INSUFFICIENT_CREDITS")

        wallet["credits"] = after

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": amount,
            "after": after,
            "reason": reason,
            "meta": meta,
        })

        return after

    return state_manager.atomic_update(mutate)


def record_ton_deposit(
    uid,
    credits,
    ton_amount,
    tx_hash,
    meta=None,
):
    """
    Atomic TON deposit authority.

    Guarantees:
    1. transaction hash can only be credited once
    2. wallet credit mutation and transaction registration happen atomically
    3. ledger entry is created
    """

    uid = str(uid)
    meta = meta or {}

    # P0 input validation: TON deposits may only create positive credits.
    if not isinstance(credits, (int, float)):
        raise TypeError("credits must be numeric")

    if credits <= 0:
        raise ValueError("INVALID_TON_CREDITS")

    if not isinstance(ton_amount, (int, float)):
        raise TypeError("ton_amount must be numeric")

    if ton_amount <= 0:
        raise ValueError("INVALID_TON_AMOUNT")

    if not isinstance(tx_hash, str) or not tx_hash.strip():
        raise ValueError("INVALID_TX_HASH")

    tx_hash = tx_hash.strip()

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        used_txs = db.setdefault("used_ton_txs", [])

        if tx_hash in used_txs:
            return None

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + credits

        wallet["credits"] = after

        used_txs.append(tx_hash)

        db.setdefault("transactions", []).append({
            "uid": uid,
            "credits": credits,
            "type": "ton",
            "ton_amount": ton_amount,
            "tx_hash": tx_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": credits,
            "after": after,
            "reason": "ton:deposit",
            "meta": {
                **meta,
                "tx_hash": tx_hash,
                "ton_amount": ton_amount,
            },
        })

        return after

    return state_manager.atomic_update(mutate)
def stake_credits(uid, amount, meta=None):
    """
    Atomically move credits into staking.

    Money invariant:
        credits decreases by amount
        staked increases by amount

    Both mutations and the ledger entry are committed together.
    """
    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    if amount <= 0:
        raise ValueError("amount must be positive")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(str(uid))

        if user is None:
            raise ValueError("user not found")

        wallet = user.setdefault("wallet", {})

        before_credits = wallet.get("credits", 0)
        before_staked = wallet.get("staked", 0)

        if before_credits < amount:
            raise ValueError("insufficient credits")

        after_credits = before_credits - amount
        after_staked = before_staked + amount

        wallet["credits"] = after_credits
        wallet["staked"] = after_staked

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": str(uid),
            "before": before_credits,
            "amount": -amount,
            "after": after_credits,
            "reason": "staking:stake",
            "meta": {
                **meta,
                "staked_before": before_staked,
                "staked_after": after_staked,
            },
        })

        return {
            "credits": after_credits,
            "staked": after_staked,
        }

    return state_manager.atomic_update(mutate)


def unstake_credits(uid, amount, meta=None):
    """
    Atomically return staked credits to the available balance.

    Money invariant:
        staked decreases by amount
        credits increases by amount

    Both mutations and the ledger entry are committed together.
    """
    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    if amount <= 0:
        raise ValueError("amount must be positive")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(str(uid))

        if user is None:
            raise ValueError("user not found")

        wallet = user.setdefault("wallet", {})

        before_credits = wallet.get("credits", 0)
        before_staked = wallet.get("staked", 0)

        if before_staked < amount:
            raise ValueError("insufficient staked balance")

        after_staked = before_staked - amount
        after_credits = before_credits + amount

        wallet["staked"] = after_staked
        wallet["credits"] = after_credits

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": str(uid),
            "before": before_credits,
            "amount": amount,
            "after": after_credits,
            "reason": "staking:unstake",
            "meta": {
                **meta,
                "staked_before": before_staked,
                "staked_after": after_staked,
            },
        })

        return {
            "credits": after_credits,
            "staked": after_staked,
        }

    return state_manager.atomic_update(mutate)


def purchase_item(
    uid,
    item,
    price,
    referrer_uid=None,
    commission_rate=0.85,
    meta=None,
):
    """
    Atomic purchase authority.

    One DB transaction performs:
    - buyer debit
    - entitlement mutation
    - optional referral commission
    - immutable ledger entries
    """

    uid = str(uid)
    price = float(price)
    meta = meta or {}

    if price <= 0:
        raise ValueError("INVALID_PRICE")

    def mutate(db):
        users = db.setdefault("users", {})

        buyer = users.get(uid)
        if buyer is None:
            raise Exception("USER_NOT_FOUND")

        buyer_wallet = buyer.setdefault("wallet", {})
        buyer_before = buyer_wallet.get("credits", 0)

        if buyer_before < price:
            raise ValueError("INSUFFICIENT_CREDITS")

        buyer_after = buyer_before - price
        buyer_wallet["credits"] = buyer_after

        if item == "ask_credit":
            buyer["ask_credits"] = buyer.get("ask_credits", 0) + 1

        elif item == "premium_agent":
            buyer["premium"] = True

        else:
            raise ValueError("UNKNOWN_ITEM")

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": buyer_before,
            "amount": -price,
            "after": buyer_after,
            "reason": f"purchase:{item}",
            "meta": dict(meta),
        })

        commission = 0

        referrer_uid = (
                db.get("users", {})
                  .get(uid, {})
                  .get("referral", {})
                  .get("referred_by")
            )
        if referrer_uid:
            referrer_uid = str(referrer_uid)

            if referrer_uid != uid and referrer_uid in users:
                commission = round(
                    price * float(commission_rate),
                    2
                )

                if commission > 0:
                    ref_user = users[referrer_uid]
                    ref_wallet = ref_user.setdefault("wallet", {})

                    ref_before = ref_wallet.get("credits", 0)
                    ref_after = ref_before + commission

                    ref_wallet["credits"] = ref_after

                    ledger.append({
                        "time": datetime.now(timezone.utc).isoformat(),
                        "uid": referrer_uid,
                        "before": ref_before,
                        "amount": commission,
                        "after": ref_after,
                        "reason": "referral:commission",
                        "meta": {
                            **meta,
                            "source_uid": uid,
                            "purchase_item": item,
                        },
                    })

                    commissions = db.setdefault("commissions", {})
                    commissions[referrer_uid] = (
                        commissions.get(referrer_uid, 0)
                        + commission
                    )

        return {
            "item": item,
            "uid": uid,
            "credits": buyer_after,
            "commission": commission,
        }

    return state_manager.atomic_update(mutate)


def record_stars_payment(
    uid,
    credits,
    stars_paid,
    currency,
    telegram_payment_charge_id,
    provider_payment_charge_id=None,
    referrer_uid=None,
    commission_rate=0.85,
    meta=None,
):
    """
    Atomic Telegram Stars payment authority.

    Idempotency key:
        telegram_payment_charge_id
    """

    uid = str(uid)
    credits = float(credits)
    stars_paid = int(stars_paid)
    currency = str(currency)
    charge_id = str(telegram_payment_charge_id or "").strip()
    provider_charge_id = (
        str(provider_payment_charge_id).strip()
        if provider_payment_charge_id
        else None
    )
    meta = meta or {}

    if credits <= 0:
        raise ValueError("INVALID_CREDITS")

    if stars_paid <= 0:
        raise ValueError("INVALID_STARS_AMOUNT")

    if not charge_id:
        raise ValueError("INVALID_CHARGE_ID")

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        transactions = db.setdefault("transactions", [])

        for tx in transactions:
            if str(tx.get("telegram_payment_charge_id", "")) == charge_id:
                return {
                    "status": "duplicate",
                    "uid": uid,
                    "credits": 0,
                    "charge_id": charge_id,
                }

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + credits
        wallet["credits"] = after

        now = datetime.now(timezone.utc).isoformat()

        transactions.append({
            "uid": uid,
            "credits": credits,
            "stars_paid": stars_paid,
            "currency": currency,
            "telegram_payment_charge_id": charge_id,
            "provider_payment_charge_id": provider_charge_id,
            "timestamp": now,
        })

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": now,
            "uid": uid,
            "before": before,
            "amount": credits,
            "after": after,
            "reason": "payment:telegram_stars",
            "meta": {
                **meta,
                "charge_id": charge_id,
                "stars_paid": stars_paid,
                "currency": currency,
            },
        })

        commission = 0

        referrer_uid = (
                db.get("users", {})
                  .get(uid, {})
                  .get("referral", {})
                  .get("referred_by")
            )
        if referrer_uid:
            referrer_uid = str(referrer_uid)

            if referrer_uid != uid and referrer_uid in users:
                commission = round(
                    credits * float(commission_rate),
                    2
                )

                if commission > 0:
                    ref_user = users[referrer_uid]
                    ref_wallet = ref_user.setdefault("wallet", {})

                    ref_before = ref_wallet.get("credits", 0)
                    ref_after = ref_before + commission

                    ref_wallet["credits"] = ref_after

                    ledger.append({
                        "time": now,
                        "uid": referrer_uid,
                        "before": ref_before,
                        "amount": commission,
                        "after": ref_after,
                        "reason": "referral:commission",
                        "meta": {
                            "source_uid": uid,
                            "charge_id": charge_id,
                        },
                    })

                    commissions = db.setdefault("commissions", {})
                    commissions[referrer_uid] = (
                        commissions.get(referrer_uid, 0)
                        + commission
                    )

        return {
            "status": "applied",
            "uid": uid,
            "credits": after,
            "commission": commission,
            "charge_id": charge_id,
        }

    return state_manager.atomic_update(mutate)


def submit_agent(uid, agent_name, reward=10, meta=None):
    """
    Atomic agent submission.

    One DB transaction:
    - creates submission
    - grants creator reward
    - writes immutable ledger entry
    """
    uid = str(uid)
    agent_name = str(agent_name).strip()
    reward = float(reward)
    meta = meta or {}

    if not agent_name:
        raise ValueError("INVALID_AGENT_NAME")

    if reward <= 0:
        raise ValueError("INVALID_REWARD")

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise ValueError("USER_NOT_FOUND")

        submissions = db.setdefault("agent_submissions", [])

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + reward
        wallet["credits"] = after

        submission = {
            "uid": uid,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        submissions.append(submission)

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": reward,
            "after": after,
            "reason": "agent:submission_reward",
            "meta": {
                **meta,
                "agent_name": agent_name,
            },
        })

        return {
            "submission": submission,
            "credits": after,
            "reward": reward,
        }

    return state_manager.atomic_update(mutate)


def approve_agent_submission(
    submission_id,
    reward=40,
    meta=None,
):
    """
    Atomic agent approval.

    One DB transaction:
    - verifies submission
    - adds marketplace entry
    - removes submission
    - rewards creator
    - writes immutable ledger
    """
    reward = float(reward)
    meta = meta or {}

    if reward <= 0:
        raise ValueError("INVALID_REWARD")

    def mutate(db):
        submissions = db.setdefault("agent_submissions", [])

        if (
            submission_id < 0
            or submission_id >= len(submissions)
        ):
            raise ValueError("SUBMISSION_NOT_FOUND")

        submission = submissions[submission_id]
        creator_uid = str(submission.get("uid"))
        agent_name = str(
            submission.get("agent_name", "")
        ).strip()

        if not creator_uid or not agent_name:
            raise ValueError("INVALID_SUBMISSION")

        users = db.setdefault("users", {})

        if creator_uid not in users:
            raise ValueError("USER_NOT_FOUND")

        marketplace = db.setdefault(
            "marketplace",
            []
        )

        now = datetime.now(timezone.utc).isoformat()

        marketplace.append({
            "name": agent_name,
            "creator": creator_uid,
            "approved_at": now,
        })

        user = users[creator_uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + reward
        wallet["credits"] = after

        del submissions[submission_id]

        db.setdefault("ledger", []).append({
            "time": now,
            "uid": creator_uid,
            "before": before,
            "amount": reward,
            "after": after,
            "reason": "agent:approval_reward",
            "meta": {
                **meta,
                "agent_name": agent_name,
                "submission_id": submission_id,
            },
        })

        return {
            "creator_uid": creator_uid,
            "agent_name": agent_name,
            "credits": after,
            "reward": reward,
        }

    return state_manager.atomic_update(mutate)


def complete_task(
    uid,
    task_id,
    meta=None,
):
    """
    Atomic task completion authority.

    One DB transaction:
    - validates task
    - prevents duplicate completion
    - marks task completed by user
    - grants reward
    - records immutable ledger entry
    """

    uid = uid
    task_id = str(task_id)
    meta = meta or {}

    def mutate(db):
        tasks = db.setdefault("tasks", {})

        if task_id not in tasks:
            raise ValueError("TASK_NOT_FOUND")

        users = db.setdefault("users", {})

        if str(uid) not in users:
            raise ValueError("USER_NOT_FOUND")

        task = tasks[task_id]
        done_by = task.setdefault("done_by", [])

        if uid in done_by or str(uid) in [str(x) for x in done_by]:
            raise ValueError("TASK_ALREADY_COMPLETED")

        reward = task.get("reward", 0)

        if not isinstance(reward, (int, float)):
            raise ValueError("INVALID_TASK_REWARD")

        if reward < 0:
            raise ValueError("INVALID_TASK_REWARD")

        done_by.append(uid)

        task["status"] = "completed"
        task["progress"] = 100
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        task["completed_by"] = str(uid)

        result = {
            "status": "completed",
            "task_id": task_id,
            "uid": str(uid),
            "reward": reward,
        }

        if reward > 0:
            user = users[str(uid)]
            wallet = user.setdefault("wallet", {})

            before = wallet.get("credits", 0)
            after = before + reward
            wallet["credits"] = after

            now = datetime.now(timezone.utc).isoformat()

            db.setdefault("ledger", []).append({
                "time": now,
                "uid": str(uid),
                "before": before,
                "amount": reward,
                "after": after,
                "reason": "task:completion_reward",
                "meta": {
                    **meta,
                    "task_id": task_id,
                },
            })

            result["credits"] = after

        return result

    return state_manager.atomic_update(mutate)


def get_staked_safe(uid):
    import json
    from pathlib import Path
    db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
    user = db.get("users", {}).get(str(uid))
    if not user:
        return 0
    return user.get("wallet", {}).get("staked", 0)
