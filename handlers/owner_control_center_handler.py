"""Owner-only, read-only SLH control center (first release).

The menu reports local runtime facts only. It never opens financial gates,
creates transactions, changes balances, merges code, or deploys services.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from core.authority import is_owner

CALLBACK_TTL_SECONDS = 30 * 60
REPORT_PATH = Path("state/control_center/last_report.json")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)

SAFE_NEXT_STEPS = [
    {
        "id": "verify_runtime_sha",
        "title": "אימות SHA של הפריסה החיה מול GitHub",
        "status": "UNKNOWN",
        "reason": "תהליך הבוט אינו שואל את Railway על פריסות חיות; האימות זמין דרך בקרת Railway החיצונית.",
    },
    {
        "id": "stars_retry_audit",
        "title": "בדיקת התאוששות רישום הכנסות Telegram Stars",
        "status": "PENDING",
        "reason": "לבדוק retry/idempotency במבחנים לפני כל שינוי.",
    },
    {
        "id": "academy_runtime",
        "title": "אימות קורס המסחר החדש בזמן ריצה",
        "status": "PENDING",
        "reason": "להשוות קטלוג קורסים, התקדמות ותצוגת משתמש בלי לשנות נתונים.",
    },
]



_ACTION_TITLES = {
    "collect_ci_evidence": "איסוף ראיות CI עדכניות",
    "collect_new_user_join_e2e_evidence": "בדיקת הצטרפות מלאה למשתמש חדש",
    "complete_bnb_opening_evidence": "השלמת ראיות BNB — השער נשאר סגור עד אימות ואישור",
}


def _action_title(action):
    action = str(action or "").strip()
    return _ACTION_TITLES.get(action, action.replace("_", " ").strip().capitalize() or "פעולה לא ידועה")


def _load_release_state():
    """Read the existing Control Center's action queue; never executes proposed actions."""
    try:
        from core.control_center import get_release_state

        raw = get_release_state()
        if not isinstance(raw, dict):
            raise ValueError("INVALID_RELEASE_STATE")

        proposals = {}
        for key in ("auto_actions", "owner_actions"):
            items = raw.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    action = str(item.get("action") or "").strip()
                    if action:
                        proposals[action] = item

        actions = []
        raw_actions = raw.get("next_actions", [])
        if isinstance(raw_actions, list):
            for raw_action in raw_actions[:10]:
                action = str(raw_action or "").strip()
                if not action:
                    continue
                proposal = proposals.get(action, {})
                mutation = proposal.get("mutation") is True
                owner_required = proposal.get("owner_required") is True
                safe = proposal.get("safe") is True
                if mutation or owner_required:
                    action_status = "OWNER_REQUIRED"
                elif safe:
                    action_status = "SAFE_PROPOSAL"
                else:
                    action_status = "REVIEW_REQUIRED"
                reason = str(proposal.get("reason") or "נדרשת בדיקת ראיות לפני ביצוע.")[:220]
                actions.append({
                    "id": action,
                    "title": _action_title(action),
                    "status": action_status,
                    "reason": reason,
                    "safe": safe,
                    "mutation": mutation,
                    "owner_required": owner_required,
                })

        def _strings(key):
            value = raw.get(key, [])
            if not isinstance(value, list):
                return []
            return [str(item)[:180] for item in value[:8] if item is not None]

        current = raw.get("current_state", {})
        current = current if isinstance(current, dict) else {}
        readiness = raw.get("readiness", {})
        readiness = readiness if isinstance(readiness, dict) else {}
        return {
            "available": True,
            "overall": str(raw.get("overall") or "UNKNOWN").upper(),
            "blockers": _strings("blockers"),
            "warnings": _strings("warnings"),
            "current_state": {str(k): str(v)[:60] for k, v in list(current.items())[:8]},
            "readiness": {str(k): str(v)[:60] for k, v in list(readiness.items())[:8]},
            "actions": actions,
        }
    except Exception as exc:
        return {
            "available": False,
            "overall": "UNKNOWN",
            "error": type(exc).__name__,
            "blockers": [],
            "warnings": [],
            "current_state": {},
            "readiness": {},
            "actions": [],
        }

def _load_ai_health(now=None):
    """Read last-known LLM status only; never call a provider or expose error bodies."""
    try:
        from core.llm_health import load_health

        raw = load_health()
        request = raw.get("last_request") if isinstance(raw, dict) else None
        request = request if isinstance(request, dict) else None
        providers = raw.get("providers", {}) if isinstance(raw, dict) else {}
        providers = providers if isinstance(providers, dict) else {}
        checked_at = str((request or {}).get("checked_at") or "")
        timestamp = datetime.fromisoformat(checked_at.replace("Z", "+00:00")) if checked_at else None
        if timestamp is not None and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        age_minutes = None
        if timestamp is not None:
            age_minutes = max(0, int((current - timestamp.astimezone(timezone.utc)).total_seconds() // 60))

        raw_status = str((request or {}).get("status") or "UNKNOWN").upper()
        if timestamp is None or age_minutes is None:
            status = "UNKNOWN"
        elif age_minutes > 60:
            status = "STALE"
        elif raw_status == "DEGRADED":
            status = "DEGRADED"
        elif raw_status == "HEALTHY":
            status = "HEALTHY"
        else:
            status = "UNKNOWN"

        providers_out = {}
        for name in ("gemini", "ollama", "groq"):
            item = providers.get(name)
            if not isinstance(item, dict):
                continue
            providers_out[name] = {
                "status": str(item.get("status") or "UNKNOWN")[:30],
                "model": str(item.get("model") or "")[:80],
                "reason_code": str(item.get("reason_code") or "unknown")[:40],
                "checked_at": str(item.get("checked_at") or "")[:40],
            }

        last_provider = str((request or {}).get("provider") or "")
        last_reason = str((request or {}).get("reason_code") or "unknown")
        return {
            "available": True,
            "status": status,
            "last_request_status": raw_status,
            "last_provider": last_provider,
            "reason_code": last_reason,
            "checked_at": checked_at or None,
            "age_minutes": age_minutes,
            "providers": providers_out,
        }
    except Exception as exc:
        return {
            "available": False,
            "status": "UNKNOWN",
            "error": type(exc).__name__,
            "last_request_status": "UNKNOWN",
            "last_provider": "",
            "reason_code": "unknown",
            "checked_at": None,
            "age_minutes": None,
            "providers": {},
        }


def callback_data(action, issued_at=None):
    """Timestamped callback payload so old inline buttons expire."""
    stamp = int(time.time() if issued_at is None else issued_at)
    return f"slhcc:{action}:{stamp}"


def parse_callback(data, now=None):
    """Return action if the payload is well-formed and still fresh."""
    parts = str(data or "").split(":")
    if len(parts) != 3 or parts[0] != "slhcc":
        return None
    action = parts[1]
    if action not in {"menu", "audit", "last", "next"}:
        return None
    try:
        issued = int(parts[2])
    except (TypeError, ValueError):
        return None
    current = int(time.time() if now is None else now)
    age = current - issued
    if age < 0 or age > CALLBACK_TTL_SECONDS:
        return None
    return action


def next_safe_step(release_state=None):
    """Select one item from the read-only live action queue; never executes it."""
    if release_state is None:
        return next(
            (item for item in SAFE_NEXT_STEPS if item["status"] != "PASS"),
            {"id": "none", "title": "אין כרגע שלב בטוח ממתין", "status": "PASS",
             "reason": "כל השלבים ברשימה הושלמו."},
        ).copy()

    if release_state.get("available") is not True:
        return {
            "id": "release_action_queue",
            "title": "בדיקת תור הפעולות אינה זמינה",
            "status": "UNKNOWN",
            "reason": "הדוח לא יוצר פעולות על סמך מצב לא מאומת. שגיאה: "
                      + str(release_state.get("error") or "UNKNOWN"),
        }

    actions = release_state.get("actions", [])
    if isinstance(actions, list) and actions:
        return dict(actions[0])

    if release_state.get("overall") == "GREEN":
        return {
            "id": "none",
            "title": "אין כרגע פעולות פתוחות בתור הבקרה",
            "status": "PASS",
            "reason": "תור הפעולות לא החזיר צעדים ממתינים.",
        }

    return {
        "id": "manual_review",
        "title": "נדרשת סקירת מצב הבקרה",
        "status": "REVIEW_REQUIRED",
        "reason": "מצב המערכת אינו GREEN, אך לא התקבלה פעולה ממוקדת בתור.",
    }


def _git_sha():
    """Prefer Railway's injected source SHA; fall back to a local Git checkout."""
    for key in ("RAILWAY_GIT_COMMIT_SHA", "GIT_COMMIT", "SOURCE_VERSION"):
        value = os.getenv(key, "").strip()
        if _SHA_RE.fullmatch(value):
            return value.lower()
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=3,
            text=True,
        ).strip()
        return value.lower() if _SHA_RE.fullmatch(value) else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def build_report():
    """Build a read-only snapshot and surface the current release action queue."""
    now = datetime.now(timezone.utc).isoformat()
    release_state = _load_release_state()
    ai_health = _load_ai_health()
    if release_state.get("available") is True and ai_health.get("status") == "DEGRADED":
        ai_action = {
            "id": "restore_ai_provider_availability",
            "title": "שחזור זמינות ספקי AI",
            "status": "OWNER_REQUIRED",
            "reason": (
                "בקשת ה־AI האחרונה נכשלה בכל הספקים. בדוק מכסות/מגבלות Gemini ו־Groq "
                "או חיבור Ollama. אל תשתף מפתחות API."
            ),
            "safe": False,
            "mutation": False,
            "owner_required": True,
        }
        existing_actions = release_state.get("actions", [])
        if not isinstance(existing_actions, list):
            existing_actions = []
        release_state["actions"] = [ai_action] + [
            item for item in existing_actions if not (isinstance(item, dict) and item.get("id") == ai_action["id"])
        ]
    queue_status = (
        release_state.get("overall", "UNKNOWN")
        if release_state.get("available") is True
        else "UNKNOWN"
    )
    queue_evidence = (
        f"blockers={len(release_state.get('blockers', []))}; "
        f"warnings={len(release_state.get('warnings', []))}; "
        f"actions={len(release_state.get('actions', []))}; "
        "proposals are display-only"
        if release_state.get("available") is True
        else "read-only action queue unavailable: " + str(release_state.get("error", "UNKNOWN"))
    )
    report = {
        "run_id": uuid.uuid4().hex[:12],
        "timestamp_utc": now,
        "runtime": {
            "cwd": os.getcwd(),
            "git_sha": _git_sha(),
        },
        "checks": [
            {
                "name": "local_runtime_snapshot",
                "status": "PASS",
                "evidence": "הדוח נוצר מתוך תהליך הבוט המקומי; לא בוצעו פעולות כתיבה עסקיות.",
            },
            {
                "name": "railway_deployment_sha",
                "status": "UNKNOWN",
                "evidence": "תהליך הבוט אינו קורא את מטא־נתוני הפריסה של Railway; אין להסיק מכך שהפריסה שגויה או תואמת.",
            },
            {
                "name": "financial_gates",
                "status": "UNKNOWN",
                "evidence": "מרכז הבקרה אינו משנה שערים; מצב הפתיחה דורש אימות פקודה נפרדת.",
            },
            {
                "name": "release_action_queue",
                "status": queue_status,
                "evidence": queue_evidence,
            },
            {
                "name": "AI provider health",
                "status": ai_health.get("status", "UNKNOWN"),
                "evidence": (
                    "last request=" + str(ai_health.get("last_request_status", "UNKNOWN"))
                    + "; reason=" + str(ai_health.get("reason_code", "unknown"))
                    + "; checked_at=" + str(ai_health.get("checked_at") or "not recorded")
                ),
            },
        ],
        "ai_health": ai_health,
        "release_state": release_state,
        "safety": {
            "mode": "READ_ONLY",
            "transactions_created": False,
            "balances_mutated": False,
            "gates_changed": False,
            "deploy_or_merge": False,
            "actions_executed": False,
        },
        "next_safe_step": next_safe_step(release_state),
    }
    return report


def save_report(report, path=REPORT_PATH):
    """Persist the last report atomically for owner follow-up."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def load_last_report(path=REPORT_PATH):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def format_report(report):
    checks = report.get("checks", [])
    lines = [
        "🧭 SLH מרכז בקרה — READ ONLY",
        f"Run: {report.get('run_id', 'UNKNOWN')}",
        f"UTC: {report.get('timestamp_utc', 'UNKNOWN')}",
        f"Git SHA: {report.get('runtime', {}).get('git_sha', 'UNKNOWN')}",
        "",
    ]
    lines.extend(
        f"{'✅' if c.get('status') == 'PASS' else '⚠️'} "
        f"{c.get('name')}: {c.get('status')} — {c.get('evidence', '')}"
        for c in checks
    )

    ai = report.get("ai_health")
    if isinstance(ai, dict):
        ai_status = str(ai.get("status") or "UNKNOWN").upper()
        if ai_status == "DEGRADED":
            lines.append("🤖 AI: DEGRADED — בקשת ה־AI האחרונה נכשלה בכל הספקים.")
            lines.append("   בדוק מכסות/מגבלות Gemini ו־Groq או חיבור Ollama; אין לשתף מפתחות.")
        elif ai_status == "HEALTHY":
            lines.append(
                "🤖 AI: HEALTHY — הבקשה האחרונה הצליחה דרך "
                + str(ai.get("last_provider") or "ספק לא ידוע")
                + "."
            )
        elif ai_status == "STALE":
            lines.append("🤖 AI: STALE — אין בדיקת בקשת AI עדכנית בשעה האחרונה.")
        else:
            lines.append("🤖 AI: UNKNOWN — עדיין לא נשמרה תוצאת בקשת AI מאומתת.")

    release = report.get("release_state")
    if isinstance(release, dict):
        lines.append("")
        if release.get("available") is True:
            lines.append("📌 תור הפעולות הנוכחי — הצעות בלבד:")
            if release.get("blockers"):
                lines.append("⛔ חוסמים: " + " · ".join(release["blockers"][:3]))
            if release.get("warnings"):
                lines.append("⚠️ אזהרות: " + " · ".join(release["warnings"][:3]))
            actions = release.get("actions", [])
            if actions:
                for action in actions[:5]:
                    owner = " · נדרש אישור OWNER" if action.get("owner_required") or action.get("mutation") else ""
                    lines.append(
                        f"➡️ {action.get('title', action.get('id', 'פעולה'))}"
                        f" [{action.get('status', 'UNKNOWN')}]"
                    )
                    lines.append("   " + str(action.get("reason") or "")[:180] + owner)
            else:
                lines.append("✅ אין פעולות ממתינות בתור הפעולות.")
            gates = release.get("current_state", {})
            if gates:
                labels = {
                    "alpha": "Alpha",
                    "bnb_settlement": "BNB settlement",
                    "ton_settlement": "TON settlement",
                }
                lines.append("🔒 שערים (מצב מדווח): " + " · ".join(
                    f"{labels.get(k, k)}={v}" for k, v in list(gates.items())[:4]
                ))
        else:
            lines.append(
                "⚠️ תור הפעולות לא אומת; לא נוצרה המלצה על סמך נתונים חסרים. "
                "שגיאה: " + str(release.get("error", "UNKNOWN"))
            )

    lines.extend([
        "",
        "🛡️ לא נשלחה עסקה, לא שונתה יתרה, לא נפתח שער ולא בוצעה פריסה.",
        "➡️ השלב הבא: " + report.get("next_safe_step", {}).get("title", "לא ידוע"),
    ])
    return "\n".join(lines)[:3900]


def _keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔎 הרץ בדיקה לקריאה בלבד", callback_data=callback_data("audit")),
        InlineKeyboardButton("📄 הצג דוח אחרון", callback_data=callback_data("last")),
        InlineKeyboardButton("➡️ המשך בטוח — הצג את השלב הבא", callback_data=callback_data("next")),
    )
    return markup


def register(bot):
    @bot.message_handler(commands=["control_center"])
    def control_command(message):
        if not is_owner(message.from_user.id):
            bot.reply_to(message, "⛔️ הפקודה מיועדת לבעלים בלבד.")
            return
        # Show the current read-only action queue immediately; do not persist on menu open.
        report = build_report()
        bot.reply_to(
            message,
            format_report(report) + "\n\nבחר פעולה להמשך.",
            reply_markup=_keyboard(),
        )

    @bot.callback_query_handler(func=lambda call: str(call.data or "").startswith("slhcc:"))
    def control_callback(call):
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔️ בעלים בלבד", show_alert=True)
            return
        action = parse_callback(call.data)
        if action is None:
            bot.answer_callback_query(call.id, "הכפתור פג תוקף. שלח /control_center מחדש.")
            return

        bot.answer_callback_query(call.id)
        if action == "menu":
            bot.send_message(call.message.chat.id, "🧭 SLH מרכז בקרה", reply_markup=_keyboard())
        elif action == "audit":
            report = build_report()
            try:
                save_report(report)
            except Exception as exc:
                report["persistence_error"] = type(exc).__name__
            bot.send_message(call.message.chat.id, format_report(report), reply_markup=_keyboard())
        elif action == "last":
            report = load_last_report()
            if not report:
                bot.send_message(call.message.chat.id, "אין עדיין דוח שמור. לחץ על בדיקה לקריאה בלבד.", reply_markup=_keyboard())
            else:
                bot.send_message(call.message.chat.id, format_report(report), reply_markup=_keyboard())
        elif action == "next":
            step = next_safe_step(_load_release_state())
            bot.send_message(
                call.message.chat.id,
                "➡️ השלב הבא בתור הפעולות\n"
                f"מצב: {step['status']}\n"
                f"משימה: {step['title']}\n"
                f"נימוק: {step['reason']}\n\n"
                "הכפתור מציג הצעה בלבד — אינו משנה קוד, פריסה, שערים או נתונים.",
                reply_markup=_keyboard(),
            )

    print("✅ owner_control_center handler registered")
