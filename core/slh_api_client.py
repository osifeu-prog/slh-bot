"""Read-only client for slh-api-production (Postgres ledger).

This module NEVER mutates state. All calls are read-only GETs.
The bot's JSON ledger (state/db.json) and the API's Postgres ledger
remain separate sources of truth. This client only surfaces what the
API knows, for display and future adapters.
"""
import os
import requests

BASE = os.getenv("SLH_API_BASE", "https://slh-api-production.up.railway.app")
TIMEOUT = 5


def _get(path, params=None):
    try:
        r = requests.get(BASE + path, params=params or {}, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        print("[slh_api] " + path + " failed: " + type(e).name)
        return None


def health():
    return _get("/api/health")


def get_user(uid):
    return _get("/api/user/full/" + str(uid))


def get_wallet(uid):
    return _get("/api/wallet/" + str(uid))


def get_balances(uid):
    return _get("/api/wallet/" + str(uid) + "/balances")


def get_transactions(uid):
    return _get("/api/transactions/" + str(uid))


def get_referrals(uid):
    return _get("/api/referral/tree/" + str(uid))


def get_referral_link(uid):
    return _get("/api/referral/link/" + str(uid))


def get_staking(uid):
    return _get("/api/staking/positions/" + str(uid))


def get_staking_plans():
    return _get("/api/staking/plans")


def get_tokenomics():
    return _get("/api/tokenomics/stats")


def get_beta_status():
    return _get("/api/beta/status")


def get_cashback(uid):
    return _get("/api/cashback/" + str(uid))


def get_marketplace_orders(uid):
    return _get("/api/marketplace/orders/" + str(uid))


def get_activity(uid):
    return _get("/api/activity/" + str(uid))


def get_rep(uid):
    return _get("/api/rep/" + str(uid))
