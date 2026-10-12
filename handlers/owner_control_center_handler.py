"""Owner-only, read-only SLH control center (first release).

The menu reports local runtime facts only. It never opens financial gates,
creates transactions, changes balances, merges code, or deploys services.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from core.authority import is_owner

CALLBACK_TTL_SECONDS = 30 * 60
REPORT_PATH = Path("state/control_center/last_report.json")

SAFE_NEXT_STEPS = [
    {
        "id": "verify_runtime_sha",
        "title": "אימות SHA של הפריסה החיה מול GitHub",
        "status": "UNKNOWN",
        "reason": "נדרש אימות פריסה חי; הרשאת Railway viewer אינה זמינה כרגע.",
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


def next_safe_step():
    """Select the first unresolved safe task; selection does not execute it."""
    return next(
        (item for item in SAFE_NEXT_STEPS if item["status"] != "PASS"),
        {"id": "none", "title": "אין כרגע שלב בטוח ממתין", "status": "PASS",
         "reason": "כל השלבים ברשימה הושלמו."},
    ).copy()


def _git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=3,
            text=True,
        ).strip()
    except Exception:
        return "UNKNOWN"


def build_report():
    """Build a read-only snapshot; external deployment/gate states stay UNKNOWN."""
    now = datetime.now(timezone.utc).isoformat()
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
                "evidence": "לא אומת מול Railway; אין להסיק שהפריסה תואמת ל-GitHub.",
            },
            {
                "name": "financial_gates",
                "status": "UNKNOWN",
                "evidence": "השערים לא נקראו ולא שונו על ידי מרכז הבקרה.",
            },
        ],
        "safety": {
            "mode": "READ_ONLY",
            "transactions_created": False,
            "balances_mutated": False,
            "gates_changed": False,
            "deploy_or_merge": False,
        },
        "next_safe_step": next_safe_step(),
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
        bot.reply_to(
            message,
            "🧭 SLH מרכז בקרה\nבחר פעולה. גרסה ראשונה: קריאה בלבד; לא משנה כספים או פריסה.",
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
            step = next_safe_step()
            bot.send_message(
                call.message.chat.id,
                "➡️ השלב הבא בתור הבטוח\n"
                f"מצב: {step['status']}\n"
                f"משימה: {step['title']}\n"
                f"נימוק: {step['reason']}\n\n"
                "הכפתור בוחר משימה בלבד — אינו משנה קוד, פריסה או נתונים.",
                reply_markup=_keyboard(),
            )

    print("✅ owner_control_center handler registered")
