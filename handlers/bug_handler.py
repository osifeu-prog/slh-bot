"""Owner-visible bug report registry.

User reports are stored in the canonical runtime DB. Owners can list and
close reports without relying on ad-hoc /exec mutations.
"""
from datetime import datetime, timezone
import re

import state_manager
from core.authority import is_owner


BUG_ID_RE = re.compile(r"^BUG_\d{8}_\d{6}_\d+$")


def is_valid_bug_id(value):
    return bool(BUG_ID_RE.fullmatch(str(value or "").strip()))


def _compact_report(report):
    report_id = str(report.get("id", "UNKNOWN"))
    uid = str(report.get("uid", "UNKNOWN"))
    status = str(report.get("status", "open")).lower()
    text = " ".join(str(report.get("text", "")).split())
    if len(text) > 180:
        text = text[:177] + "..."
    return report_id, uid, status, text


def render_bug_reports(reports, status_filter="open", max_chars=3500):
    wanted = str(status_filter or "open").strip().lower()
    if wanted not in {"open", "closed", "all"}:
        wanted = "open"

    selected = []
    for report in reversed(list(reports or [])):
        status = str(report.get("status", "open")).lower()
        if wanted != "all" and status != wanted:
            continue
        selected.append(report)

    header = {
        "open": "🐞 Bugs פתוחים",
        "closed": "✅ Bugs סגורים",
        "all": "🐞 Bug Registry",
    }[wanted]

    if not selected:
        return f"{header}: 0"

    lines = [f"{header}: {len(selected)}"]
    for report in selected:
        report_id, uid, status, text = _compact_report(report)
        icon = "🟠" if status == "open" else "✅"
        line = f"{icon} {report_id} | uid={uid}\n{text or '(ללא תיאור)'}"
        if sum(len(x) + 1 for x in lines) + len(line) + 1 > max_chars:
            lines.append(f"... מוצגים {len(lines) - 1} מתוך {len(selected)}")
            break
        lines.append(line)
    return "\n".join(lines)


def close_bug_record(reports, report_id, closed_by, note=""):
    target = str(report_id or "").strip()
    if not is_valid_bug_id(target):
        return {"ok": False, "reason": "invalid_id"}
    for report in reports:
        if str(report.get("id", "")).strip() != target:
            continue
        if str(report.get("status", "open")).lower() == "closed":
            return {"ok": False, "reason": "already_closed", "report": report}
        report["status"] = "closed"
        report["closed_at"] = datetime.now(timezone.utc).isoformat()
        report["closed_by"] = str(closed_by)
        if note:
            report["resolution"] = str(note).strip()[:500]
        return {"ok": True, "report": report}
    return {"ok": False, "reason": "not_found"}


def register(bot):
    @bot.message_handler(commands=["bug"])
    def bug_cmd(message):
        raw = (message.text or "").split(maxsplit=1)
        if len(raw) < 2 or not raw[1].strip():
            bot.reply_to(message, "🐞 שימוש: /bug <תיאור התקלה>")
            return

        report_id = "BUG_%s_%s" % (
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            message.message_id,
        )
        text = raw[1].strip()
        uid = str(message.from_user.id)

        def mutate(db):
            reports = db.setdefault("bug_reports", [])
            reports.append({
                "id": report_id,
                "uid": uid,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": text,
                "status": "open",
            })
            return report_id

        state_manager.atomic_update(mutate)
        bot.reply_to(message, f"🐞 הדיווח נקלט: {report_id}")

    @bot.message_handler(commands=["list_bugs"])
    def list_bugs_cmd(message):
        if not is_owner(message):
            bot.reply_to(message, "⛔ OWNER only")
            return
        parts = (message.text or "").split()
        status_filter = parts[1].lower() if len(parts) > 1 else "open"
        if status_filter not in {"open", "closed", "all"}:
            bot.reply_to(message, "שימוש: /list_bugs [open|closed|all]")
            return
        db = state_manager.load_db()
        reports = db.get("bug_reports", [])
        bot.reply_to(message, render_bug_reports(reports, status_filter=status_filter))

    @bot.message_handler(commands=["close_bug"])
    def close_bug_cmd(message):
        if not is_owner(message):
            bot.reply_to(message, "⛔ OWNER only")
            return
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /close_bug <BUG_ID> [resolution]")
            return

        report_id = parts[1].strip()
        note = parts[2].strip() if len(parts) > 2 else ""
        closed_by = str(message.from_user.id)

        def mutate(db):
            reports = db.setdefault("bug_reports", [])
            return close_bug_record(reports, report_id, closed_by, note)

        result = state_manager.atomic_update(mutate)
        reason = result.get("reason")
        if result.get("ok"):
            bot.reply_to(message, f"✅ נסגר {report_id}")
        elif reason == "invalid_id":
            bot.reply_to(message, "❌ BUG_ID לא תקין.")
        elif reason == "not_found":
            bot.reply_to(message, f"❌ הבאג {report_id} לא נמצא.")
        elif reason == "already_closed":
            bot.reply_to(message, f"ℹ️ הבאג {report_id} כבר סגור.")
        else:
            bot.reply_to(message, "❌ סגירת הבאג נכשלה בבטחה.")

    print("bug_handler loaded")
