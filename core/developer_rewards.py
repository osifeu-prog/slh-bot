"""Canonical rewards for verified Developer Lab pull requests."""

from __future__ import annotations

import os
import requests

import state_manager
from core import economy_service
from core.authority import is_owner

REPO = str(os.getenv("SLH_GITHUB_REPOSITORY", "osifeu-prog/slh-bot")).strip()
BASE_BRANCH = str(os.getenv("SLH_DEVELOPER_LAB_BASE", "main")).strip() or "main"
REWARDS_KEY = "developer_rewards"


def _headers():
    token = str(os.getenv("GIT_TOKEN", "")).strip()
    if not token:
        raise RuntimeError("GIT_TOKEN_MISSING")
    return {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SLH-Developer-Rewards",
    }


def _github_get(path, **params):
    response = requests.get(
        "https://api.github.com" + path,
        headers=_headers(),
        params=params or None,
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"GITHUB_HTTP_{response.status_code}")
    return response.json()


def verify_merged_pr(uid, pr_number):
    uid = str(uid)
    try:
        pr_number = int(pr_number)
    except (TypeError, ValueError):
        raise ValueError("INVALID_PR_NUMBER")
    if pr_number <= 0:
        raise ValueError("INVALID_PR_NUMBER")

    pr = _github_get(f"/repos/{REPO}/pulls/{pr_number}")
    if not pr.get("merged_at"):
        raise ValueError("PR_NOT_MERGED")
    if str((pr.get("base") or {}).get("ref") or "") != BASE_BRANCH:
        raise ValueError("PR_BASE_NOT_MAIN")

    head_ref = str((pr.get("head") or {}).get("ref") or "")
    body = str(pr.get("body") or "")
    expected_marker = f"Developer UID: {uid}"
    if not (head_ref.startswith(f"dev/{uid}/") or expected_marker in body):
        raise ValueError("PR_NOT_FROM_DEVELOPER_LAB")

    return {
        "pr_number": pr_number,
        "uid": uid,
        "title": str(pr.get("title") or ""),
        "url": pr.get("html_url"),
        "merged_at": pr.get("merged_at"),
        "head_ref": head_ref,
        "base_ref": BASE_BRANCH,
    }


def apply_merged_pr_reward(uid, pr_number):
    uid = str(uid)
    proof = verify_merged_pr(uid, pr_number)

    db = state_manager.load_db()
    rows = db.get(REWARDS_KEY, {}) or {}
    key = f"{uid}:{proof['pr_number']}"
    existing = rows.get(key)
    if isinstance(existing, dict):
        return {
            "ok": True,
            "status": "already_rewarded",
            "uid": uid,
            "pr_number": proof["pr_number"],
            "reward_credits": float(existing.get("reward_credits", 0)),
            "contribution_number": int(existing.get("contribution_number", 0)),
            "balance": existing.get("balance"),
            "milestone_3pr": bool(existing.get("milestone_3pr")),
            "pr_url": proof["url"],
        }

    contribution_number = sum(
        1 for item in rows.values()
        if isinstance(item, dict) and str(item.get("uid")) == uid
    ) + 1
    reward_credits = 5000.0 if contribution_number == 1 else 2500.0
    idempotency_key = f"developer-pr-reward:{uid}:{proof['pr_number']}"

    balance = economy_service.record_transaction(
        uid=uid,
        amount=reward_credits,
        reason="developer:merged_pr_reward",
        meta={
            "source": "developer_lab",
            "pr_number": proof["pr_number"],
            "pr_url": proof["url"],
            "contribution_number": contribution_number,
            "idempotency_key": idempotency_key,
        },
    )

    record = {
        "uid": uid,
        "pr_number": proof["pr_number"],
        "pr_url": proof["url"],
        "merged_at": proof["merged_at"],
        "reward_credits": reward_credits,
        "contribution_number": contribution_number,
        "balance": balance,
        "milestone_3pr": contribution_number >= 3,
    }

    def mutate(state):
        rewards = state.setdefault(REWARDS_KEY, {})
        if key in rewards:
            return rewards[key]
        rewards[key] = record
        return record

    saved = state_manager.atomic_update(mutate)
    return {
        "ok": True,
        "status": "rewarded",
        **saved,
        "reward_credits": float(saved.get("reward_credits", reward_credits)),
        "contribution_number": int(saved.get("contribution_number", contribution_number)),
        "balance": saved.get("balance", balance),
        "milestone_3pr": bool(saved.get("milestone_3pr", False)),
    }
