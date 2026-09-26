"""SLH Action Trust Gate.

Pure policy evaluation for sensitive actions. This module does not execute
anything and does not grant credentials. Callers must separately enforce their
real authorization and confirmation mechanisms.
"""

from typing import Any


SENSITIVE_ACTIONS = {
    "wallet_send",
    "wallet_bind",
    "payment",
    "payout",
    "exchange_order",
    "external_tool",
    "deployment",
    "secret_access",
}


def evaluate(
    *,
    action: str,
    authenticated: bool,
    authorized: bool,
    user_confirmed: bool = False,
    trust_level: str = "low",
    external_content: bool = False,
    money_involved: bool = False,
) -> dict[str, Any]:
    """Return a policy decision without executing or authorizing the action."""

    action = str(action or "").strip().lower()
    trust_level = str(trust_level or "low").strip().lower()

    reasons: list[str] = []

    if not action:
        reasons.append("missing_action")
    if not authenticated:
        reasons.append("authentication_required")
    if not authorized:
        reasons.append("authorization_required")
    if trust_level == "high":
        reasons.append("high_trust_risk")
    if external_content and action in SENSITIVE_ACTIONS:
        reasons.append("untrusted_external_content")
    if money_involved and not user_confirmed:
        reasons.append("explicit_user_confirmation_required")
    if action in SENSITIVE_ACTIONS and not user_confirmed:
        reasons.append("sensitive_action_confirmation_required")

    if any(
        reason in reasons
        for reason in (
            "missing_action",
            "authentication_required",
            "authorization_required",
            "high_trust_risk",
        )
    ):
        decision = "BLOCK"
    elif reasons:
        decision = "REVIEW"
    else:
        decision = "ALLOW"

    return {
        "decision": decision,
        "action": action,
        "reasons": reasons,
        "execution_permitted": decision == "ALLOW",
        "execution_performed": False,
    }


def is_sensitive(action: str) -> bool:
    return str(action or "").strip().lower() in SENSITIVE_ACTIONS
