"""Bounded voice-driven operator checks.

This router permits only canonical read-only checks. It never changes balances,
orders, wallets, settlement gates, broadcasts, or device commands.
"""
from __future__ import annotations

import re
from typing import Any


_ALLOWED_ROLES = {"OWNER", "ADMIN", "DEVELOPER"}
_READ_ONLY_FOOTER = "\n\n🔒 READ ONLY — לא בוצעו שינויים, לא נשלחו עסקאות ולא שונו שערים."

_ALIASES = {
    "exchange": (
        "בדוק את הבורסה", "בדוק בורסה", "מצב הבורסה", "בדיקת בורסה",
        "בדוק את המסחר הפנימי", "בדוק מסחר פנימי", "check exchange",
        "exchange status", "check internal exchange",
    ),
    "bnb": ("בדוק bnb", "בדיקת bnb", "מצב bnb", "bnb status", "check bnb", "bnb check"),
    "ton": ("בדוק ton", "בדיקת ton", "מצב ton", "ton status", "check ton", "ton check"),
    "money": (
        "בדוק כסף", "בדיקת כסף", "בדוק את הכסף", "בדוק ledger",
        "בדיקת ledger", "check money", "money check",
    ),
    "ux": (
        "בדוק ux", "בדיקת ux", "בדוק כפתורים", "בדוק ממשק",
        "בדיקת ממשק", "check ux",
    ),
    "mcp": (
        "בדוק חיבורי האוטומציה", "בדוק חיבור אוטומציה",
        "בדיקת חיבור אוטומציה", "בדוק חיבור mcp", "בדוק mcp",
        "mcp status", "check mcp", "check automation",
    ),
    "go_live": (
        "בדוק דוח go live", "דוח go live", "בדוק go live",
        "בדוק מוכנות להשקה", "דוח מוכנות להשקה", "go live report",
        "release report", "check go live",
    ),
    "system": (
        "בדוק את כל המערכת", "בדוק כל המערכת", "בדוק את המערכת",
        "בדוק מערכת", "בדיקת מערכת", "מצב מערכת", "system check",
        "run system check", "check system",
    ),
}

_MUTATION_VERBS = (
    "פתח", "תפתח", "הפעל", "תפעיל", "שלח", "העבר", "העבר לי", "בצע",
    "תבצע", "קנה", "מכור", "משוך", "תמשוך", "שדר", "תשדר",
    "open", "enable", "send", "transfer", "buy", "sell", "withdraw",
    "broadcast", "execute",
)
_FINANCIAL_SCOPES = (
    "bnb", "ton", "slh", "credits", "credit", "קרדיט", "קרדיטים", "כסף",
    "ארנק", "wallet", "settlement", "מסחר", "בורסה", "ברודקאסט", "broadcast",
    "gate", "שער",
)


def _normalize(text: str) -> str:
    value = str(text or "").lower()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _safe_result(name: str, result: Any) -> str:
    if not isinstance(result, dict):
        return f"🟡 {name}: תוצאת בדיקה לא תקינה."
    ok = result.get("ok") is True
    detail = re.sub(r"[\x00-\x1f]+", " ", str(result.get("detail") or "אין פירוט"))
    detail = detail[:420]
    return f"{'✅' if ok else '🟡'} {name}: {detail}"


def _run_check(kind: str, uid: str) -> str:
    if kind == "mcp":
        try:
            from handlers.mcp_proof_handler import read_mcp_proof

            result = read_mcp_proof()
        except Exception as exc:
            result = {"ok": False, "detail": f"MCP proof failed safely ({type(exc).__name__})"}
        return (
            "🔎 SLH OS — בדיקת חיבור האוטומציה הקולית (READ ONLY)\n"
            + _safe_result("MCP Control Plane", result)
            + _READ_ONLY_FOOTER
        )

    if kind == "go_live":
        try:
            from handlers.system_checks_handler import _go_live_report_output

            return _go_live_report_output(uid)
        except Exception as exc:
            return (
                f"⛔ דוח Go-Live נכשל בבטחה ({type(exc).__name__})."
                + _READ_ONLY_FOOTER
            )

    from core import system_checks

    checks = {
        "exchange": ("Internal Exchange", lambda: system_checks.check_exchange()),
        "bnb": ("BNB", lambda: system_checks.check_bnb()),
        "ton": ("TON", lambda: system_checks.check_ton(uid)),
        "money": ("Money / invariants", lambda: system_checks.check_money(uid)),
        "ux": ("Mini App UX", lambda: system_checks.check_ux()),
    }

    if kind == "system":
        items = [
            ("DB", system_checks.check_db),
            ("Commands", system_checks.check_commands),
            ("Mini App UX", system_checks.check_ux),
            ("Money / invariants", lambda: system_checks.check_money(uid)),
            ("BNB", system_checks.check_bnb),
            ("TON", lambda: system_checks.check_ton(uid)),
            ("Internal Exchange", system_checks.check_exchange),
        ]
        lines = ["🧪 SLH OS — בדיקת מערכת קולית (READ ONLY)", ""]
        for name, fn in items:
            try:
                lines.append(_safe_result(name, fn()))
            except Exception as exc:
                lines.append(f"⛔ {name}: בדיקה נכשלה ({type(exc).__name__})")
        return "\n".join(lines) + _READ_ONLY_FOOTER

    name, fn = checks[kind]
    try:
        result = fn()
    except Exception as exc:
        result = {"ok": False, "detail": f"בדיקה נכשלה ({type(exc).__name__})"}

    extra = ""
    if kind == "bnb" and isinstance(result, dict):
        gate = "OPEN" if result.get("public_open") is True else "CLOSED"
        evidence = str(result.get("empirical_status") or result.get("status") or "UNKNOWN")
        launch_ready = "כן" if result.get("launch_ready") is True else "לא"
        extra = f"\nשער ציבורי: {gate} · הוכחת settlement: {evidence} · מוכן ל־Go-Live: {launch_ready}"
    elif kind == "exchange" and isinstance(result, dict):
        gate = "OPEN" if result.get("public_open", result.get("verdict") == "OPEN") is True else "CLOSED"
        extra = f"\nשער מסחר פנימי: {gate}"

    return "🔎 SLH OS — בדיקה קולית\n" + _safe_result(name, result) + extra + _READ_ONLY_FOOTER


def route_voice_operator_request(text: str, uid: str | int | None) -> str | None:
    """Map a small, explicit set of voice phrases to read-only operator checks.

    Returns None for ordinary conversation, so normal conversational routing
    remains unchanged. Financial mutations and broadcasts are always rejected
    here; they are never inferred from an LLM response.
    """
    normalized = _normalize(text)
    if not normalized:
        return None

    if _contains_any(normalized, _MUTATION_VERBS) and _contains_any(normalized, _FINANCIAL_SCOPES):
        return (
            "⛔ לא בוצעה פעולה. פקודות קוליות לשינוי יתרות, להעברת נכסים, לפתיחת שערים "
            "או לשליחת ברודקאסט חסומות דרך הנתיב הקולי הכללי. מצב השער נבדק בנפרד ואינו משתנה "
            "בעקבות בקשת שינוי קולית.\nאפשר לומר: ״בדוק BNB״ או ״בדוק את הבורסה״ לקבלת בדיקה "
            "קנונית ועדכנית לקריאה בלבד."
        )

    kind = next(
        (name for name, phrases in _ALIASES.items() if _contains_any(normalized, phrases)),
        None,
    )
    if kind is None:
        return None

    from core.authority import get_role
    role = get_role(str(uid or ""))
    if role not in _ALLOWED_ROLES:
        return "⛔ בדיקות תפעוליות קוליות זמינות רק ל־OWNER/ADMIN/DEVELOPER. לא ניגשתי לנתוני המערכת."

    return _run_check(kind, str(uid or ""))
