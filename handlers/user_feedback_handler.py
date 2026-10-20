"""Explicit, opt-in bug report and suggestion commands (no LLM required)."""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import state_manager

OWNER_UID = os.getenv("SLH_OWNER_UID", "8789977826").strip()
MAX_REPORT_LENGTH = 2000

_CATEGORIES = [
    ("bug", ["לא עובד", "שגיאה", "באג", "תקלה", "error", "bug", "broken", "תקוע"]),
    ("feature", ["תוסיפו", "רעיון", "הצעה", "feature", "suggestion", "idea"]),
    ("question", ["איך", "מה זה", "למה", "מתי", "איפה", "האם", "?", "how", "what", "why"]),
    ("complaint", ["לא טוב", "בעיה", "גרוע", "bad", "disappointed"]),
]

_REPLIES = {
    "bug": "🐞 תודה על הדיווח! שמרתי אותו והעברתי לבעלים לבדיקה.",
    "feature": "💡 תודה על ההצעה! שמרתי אותה והעברתי לבעלים לבדיקה.",
    "question": "❓ תודה. שמרתי את השאלה להעברה לבעלים.",
    "complaint": "🙏 תודה על המשוב. שמרתי אותו להעברה לבעלים.",
    "general": "📩 תודה. שמרתי את ההודעה להעברה לבעלים.",
}


def _classify(text: str) -> str:
    low = (text or "").strip().lower()
    for category, keywords in _CATEGORIES:
        if any(keyword in low for keyword in keywords):
            return category
    return "general"


def _normalize_for_fingerprint(text: str) -> str:
    return re.sub(r"\W+", " ", str(text or "").casefold(), flags=re.UNICODE).strip()


def _component_for_report(text: str) -> str:
    low = str(text or "").casefold()
    rules = (
        ("exchange", ("exchange", "buy_slh", "sell_slh", "קניית slh", "לקנות slh", "קנה slh", "אין הרשאה", "מסחר", "בורסה")),
        ("staking", ("staking", "stake", "סטייקינג", "סטייק", "stake_lock", "positions")),
        ("synth", ("synth", "סינתיסייזר", "פסנתר", "כפתור חזרה", "מנגינה")),
        ("payments", ("stars", "xtr", "payplus", "כרטיס אשראי", "תשלום", "חיוב", "הפקדה", "bnb", "ton")),
        ("mini_app", ("mini app", "mini-app", "miniapp", "webapp", "button", "כפתור", "מסך")),
    )
    for component, keywords in rules:
        if any((re.search(r"\bton\b", low) is not None) if keyword == "ton" else keyword in low for keyword in keywords):
            return component
    return "other"


def _priority_for_report(text: str, component: str) -> str:
    low = str(text or "").casefold()
    critical = (
        "חיוב כפול", "כסף נעלם", "יתרה נעלמה", "נפרץ", "גניבה",
        "private key", "seed phrase", "double charge", "funds lost",
        "unauthorized transfer", "security breach",
    )
    if any(token in low for token in critical):
        return "P0"
    if component in {"exchange", "payments"}:
        return "P1"
    if component in {"staking", "synth", "mini_app"}:
        return "P2"
    return "P3"


def _run_read_only_diagnostic(component: str) -> dict:
    """Run only a registered, bounded, read-only check. Never accepts arbitrary code."""
    checked_at = datetime.now(timezone.utc).isoformat()
    root = Path(__file__).resolve().parents[1]
    try:
        if component == "exchange":
            from core.system_checks import check_exchange

            result = check_exchange()
            gate = str(result.get("public_gate") or "UNKNOWN").upper()
            verdict = str(result.get("verdict") or "UNKNOWN").upper()
            public_ready = result.get("public_ready") is True
            status = (
                "PASS"
                if result.get("ok") is True and public_ready and gate == "OPEN" and verdict == "OPEN"
                else "BLOCKED"
            )
            return {
                "status": status,
                "scope": "read_only_local_snapshot",
                "check": "core.system_checks.check_exchange",
                "checked_at": checked_at,
                "evidence": {
                    "public_gate": gate,
                    "public_ready": public_ready,
                    "verdict": verdict,
                    "readiness_only": bool(result.get("ok") is True and public_ready and gate != "OPEN"),
                    "detail": str(result.get("detail") or "no detail")[:300],
                    "account_ledger_status": str(result.get("account_ledger_status") or "UNKNOWN"),
                    "account_ledger_blockers": [
                        str(item)[:120]
                        for item in (result.get("account_ledger_blockers") or [])[:5]
                    ],
                },
            }

        if component == "synth":
            page = (root / "synth_ui.html").read_text(encoding="utf-8")
            has_back_button = 'id="back"' in page
            has_back_handler = "$('back').addEventListener" in page
            has_return_route = "window.location.assign('/mini-app-v4')" in page
            passed = has_back_button and has_back_handler and has_return_route
            return {
                "status": "PASS" if passed else "FAIL",
                "scope": "source_contract_only",
                "check": "synth_back_button_contract",
                "checked_at": checked_at,
                "evidence": {
                    "back_button_present": has_back_button,
                    "back_handler_present": has_back_handler,
                    "mini_app_return_route_present": has_return_route,
                    "limitation": "A source pass does not reproduce the reporter's client, cache, or Telegram runtime.",
                },
            }

        if component == "staking":
            page = (root / "mini_app.html").read_text(encoding="utf-8")
            handler = (root / "handlers" / "staking_handler.py").read_text(encoding="utf-8")
            api = (root / "webapp.py").read_text(encoding="utf-8")
            has_form = (
                'id="stake" class="screen"' in page
                and "function submitStake()" in page
                and "fetch('/api/v1/staking'" in page
            )
            has_api = '@app.route("/api/v1/staking", methods=["POST"])' in api
            has_direct_button = (
                'commands=["staking"]' in handler
                and "types.WebAppInfo(url=target)" in handler
                and '("screen", "stake")' in handler
            )
            passed = has_form and has_api and has_direct_button
            return {
                "status": "PASS" if passed else "FAIL",
                "scope": "source_contract_only",
                "check": "credits_staking_entrypoint_contract",
                "checked_at": checked_at,
                "evidence": {
                    "mini_app_form_present": has_form,
                    "authenticated_staking_api_present": has_api,
                    "telegram_direct_staking_button_present": has_direct_button,
                },
            }

        if component == "mini_app":
            page = (root / "mini_app.html").read_text(encoding="utf-8")
            route = (root / "webapp.py").read_text(encoding="utf-8")
            route_present = '@app.route("/mini-app-v4")' in route
            page_present = "function show(" in page and 'id="home"' in page
            return {
                "status": "PASS" if route_present and page_present else "FAIL",
                "scope": "source_contract_only",
                "check": "mini_app_route_contract",
                "checked_at": checked_at,
                "evidence": {
                    "v4_route_present": route_present,
                    "home_screen_present": page_present,
                    "limitation": "A source pass does not prove the reporter's client runtime or connectivity.",
                },
            }

        if component == "payments":
            return {
                "status": "UNKNOWN",
                "scope": "read_only",
                "check": "payment_diagnostic_not_auto_executed",
                "checked_at": checked_at,
                "evidence": {
                    "reason": "Requires a specific order/payment identifier; no payment, refund, claim, or gate mutation is performed automatically."
                },
            }

        return {
            "status": "UNKNOWN",
            "scope": "read_only",
            "check": "no_registered_diagnostic",
            "checked_at": checked_at,
            "evidence": {"reason": "No safe registered diagnostic matches this component."},
        }
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "scope": "read_only",
            "check": f"{component}_diagnostic",
            "checked_at": checked_at,
            "evidence": {"reason": f"diagnostic failed safely: {type(exc).__name__}"},
        }


def _triage_report(text: str, category: str) -> dict | None:
    if str(category or "").lower() != "bug":
        return None
    component = _component_for_report(text)
    normalized = _normalize_for_fingerprint(text)
    fingerprint = hashlib.sha256(
        f"{component}|{normalized}".encode("utf-8", "replace")
    ).hexdigest()
    return {
        "component": component,
        "priority": _priority_for_report(text, component),
        "confidence": "HIGH" if component != "other" else "LOW",
        "fingerprint": fingerprint,
        "diagnostic": _run_read_only_diagnostic(component),
    }


def _record(uid, username, first_name, text, category, triage=None) -> dict:
    safe_text = str(text or "").strip()[:MAX_REPORT_LENGTH]
    if triage is None and str(category or "").lower() == "bug":
        triage = _triage_report(safe_text, category)
    triage = dict(triage) if isinstance(triage, dict) else None

    def mutate(db):
        feedback = db.setdefault("user_feedback", [])
        if not isinstance(feedback, list):
            raise ValueError("USER_FEEDBACK_STORE_INVALID")
        tasks = db.setdefault("bug_triage_tasks", [])
        if not isinstance(tasks, list):
            raise ValueError("BUG_TRIAGE_TASK_STORE_INVALID")

        next_id = max(
            (int(item.get("id", 0) or 0) for item in feedback if isinstance(item, dict)),
            default=0,
        ) + 1
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "id": next_id,
            "uid": str(uid),
            "username": str(username or "")[:128],
            "first_name": str(first_name or "")[:128],
            "text": safe_text,
            "category": str(category),
            "status": "NEW",
            "created_at": now,
        }

        task_id = None
        task_status = None
        if triage is not None:
            component = str(triage.get("component") or "other")
            fingerprint = str(triage.get("fingerprint") or "")
            if not fingerprint:
                fingerprint = hashlib.sha256(
                    f"{component}|{_normalize_for_fingerprint(safe_text)}".encode("utf-8", "replace")
                ).hexdigest()
            task = next(
                (
                    item for item in reversed(tasks)
                    if isinstance(item, dict)
                    and str(item.get("fingerprint") or "") == fingerprint
                    and str(item.get("status") or "OPEN").upper() in {"OPEN", "IN_PROGRESS"}
                ),
                None,
            )
            if task is None:
                next_task_no = max(
                    (
                        int(match.group(1))
                        for item in tasks if isinstance(item, dict)
                        for match in [re.fullmatch(r"BUGTASK_(\d{6})", str(item.get("id") or ""))]
                        if match
                    ),
                    default=0,
                ) + 1
                task_id = f"BUGTASK_{next_task_no:06d}"
                task = {
                    "id": task_id,
                    "fingerprint": fingerprint,
                    "title": " ".join(safe_text.split())[:180],
                    "component": component,
                    "priority": str(triage.get("priority") or "P3"),
                    "confidence": str(triage.get("confidence") or "LOW"),
                    "status": "OPEN",
                    "report_ids": [next_id],
                    "diagnostic": triage.get("diagnostic") if isinstance(triage.get("diagnostic"), dict) else {
                        "status": "UNKNOWN", "scope": "read_only", "check": "diagnostic_missing"
                    },
                    "created_at": now,
                    "updated_at": now,
                    "duplicate_count": 0,
                }
                tasks.append(task)
                task_status = "CREATED"
            else:
                task_id = str(task.get("id") or "")
                report_ids = task.setdefault("report_ids", [])
                if next_id not in report_ids:
                    report_ids.append(next_id)
                task["updated_at"] = now
                task["diagnostic"] = triage.get("diagnostic") if isinstance(triage.get("diagnostic"), dict) else task.get("diagnostic")
                task["duplicate_count"] = int(task.get("duplicate_count", 0) or 0) + 1
                task_status = "DUPLICATE_LINKED"

            entry["triage"] = {
                "component": component,
                "priority": str(triage.get("priority") or "P3"),
                "confidence": str(triage.get("confidence") or "LOW"),
                "diagnostic": task.get("diagnostic"),
                "task_id": task_id,
                "task_status": task_status,
                "fingerprint": fingerprint,
            }

        feedback.append(entry)
        if len(feedback) > 1000:
            del feedback[:-1000]
        return {
            "ok": True,
            "id": next_id,
            "total": len(feedback),
            "triage": entry.get("triage"),
        }

    return state_manager.atomic_update(mutate)


def _notify_owner(bot, uid, first_name, username, text, category, feedback_id, triage=None):
    owner_uid = OWNER_UID
    if not owner_uid or not owner_uid.isdigit() or str(uid) == owner_uid:
        return
    icon = {"bug": "🐞", "feature": "💡", "question": "❓", "complaint": "🙏"}.get(category, "📩")
    body = (
        f"{icon} דיווח חדש #{feedback_id}\n"
        f"סוג: {category}\n"
        f"מאת: {str(first_name or 'משתמש')[:128]} (@{str(username or '—')[:128]})\n"
        f"UID: {uid}\n"
        "──────────\n"
        f"{str(text or '')[:800]}"
    )
    if isinstance(triage, dict):
        diagnostic = triage.get("diagnostic") if isinstance(triage.get("diagnostic"), dict) else {}
        task_line = (
            f"\n🧭 Auto-triage: {triage.get('component', 'other')} · "
            f"{triage.get('priority', 'P3')} · confidence={triage.get('confidence', 'LOW')}"
            f"\n🔎 Read-only check: {diagnostic.get('status', 'UNKNOWN')} "
            f"({diagnostic.get('check', 'no_registered_diagnostic')})"
            f"\n🗂 Task: {triage.get('task_id', 'not-created')} · /bug_queue"
        )
        body += task_line
    try:
        bot.send_message(int(owner_uid), body)
    except Exception as exc:
        # Persisted feedback is the source of truth even if the alert cannot be delivered.
        print(f"USER_FEEDBACK_NOTIFY_FAIL: {type(exc).__name__}")


def register(bot):
    """Register explicit commands only; ordinary conversation remains available to AI handlers."""
    @bot.message_handler(commands=["bugreport", "suggest"], content_types=["text"])
    def handle_feedback(message):
        try:
            raw = str(getattr(message, "text", "") or "").strip()
            command, _, body = raw.partition(" ")
            command = command.split("@", 1)[0].lower().lstrip("/")
            report = body.strip()[:MAX_REPORT_LENGTH]
            if not report:
                command_example = "/suggest" if command == "suggest" else "/bugreport"
                bot.reply_to(
                    message,
                    f"📝 הוסף פרטים אחרי הפקודה. לדוגמה: {command_example} הכפתור לא עובד",
                    parse_mode=None,
                )
                return

            user = getattr(message, "from_user", None)
            uid = str(getattr(user, "id", "") or "")
            if not uid.isdigit():
                bot.reply_to(message, "⛔ לא הצלחתי לאמת את חשבון Telegram. לא נשמר דיווח.", parse_mode=None)
                return
            username = str(getattr(user, "username", "") or "")
            first_name = str(getattr(user, "first_name", "") or "")
            category = "feature" if command == "suggest" else "bug"
            result = _record(uid, username, first_name, report, category)
            feedback_id = result.get("id", 0)
            persisted_triage = result.get("triage") if isinstance(result.get("triage"), dict) else None
            bot.reply_to(
                message,
                f"{_REPLIES[category]}\nמספר דיווח: #{feedback_id}",
                parse_mode=None,
            )
            _notify_owner(bot, uid, first_name, username, report, category, feedback_id, persisted_triage)
        except Exception as exc:
            print(f"USER_FEEDBACK_HANDLER_ERROR: {type(exc).__name__}")
            try:
                bot.reply_to(message, "⛔ לא הצלחתי לשמור את הדיווח. נסה שוב מאוחר יותר.", parse_mode=None)
            except Exception:
                pass

    @bot.message_handler(commands=["bug_queue"])
    def bug_queue_cmd(message):
        from core.authority import is_owner
        if not is_owner(message):
            bot.reply_to(message, "⛔ OWNER only", parse_mode=None)
            return
        db = state_manager.load_db()
        tasks = db.get("bug_triage_tasks", [])
        if not isinstance(tasks, list):
            bot.reply_to(message, "⛔ BUG_TASK_STORE_INVALID", parse_mode=None)
            return
        selected = [
            task for task in reversed(tasks)
            if isinstance(task, dict) and str(task.get("status") or "OPEN").upper() in {"OPEN", "IN_PROGRESS"}
        ]
        if not selected:
            bot.reply_to(message, "✅ אין משימות Bug פתוחות.", parse_mode=None)
            return
        lines = [f"🧭 Bug triage queue · open={len(selected)}"]
        for task in selected[:20]:
            diagnostic = task.get("diagnostic") if isinstance(task.get("diagnostic"), dict) else {}
            evidence = diagnostic.get("evidence") if isinstance(diagnostic.get("evidence"), dict) else {}
            detail = str(evidence.get("detail") or evidence.get("reason") or "")
            if len(detail) > 130:
                detail = detail[:127] + "..."
            lines.append(
                f"\n{task.get('id')} · {task.get('priority', 'P3')} · "
                f"{task.get('component', 'other')} · {diagnostic.get('status', 'UNKNOWN')}"
                f"\nדיווחים: {len(task.get('report_ids') or [])} · {str(task.get('title') or '')[:150]}"
                + (f"\n{detail}" if detail else "")
            )
        lines.append("\nסגירה: /close_bug_task <BUGTASK_ID> <resolution>")
        bot.reply_to(message, "\n".join(lines)[:3800], parse_mode=None)

    @bot.message_handler(commands=["close_bug_task"])
    def close_bug_task_cmd(message):
        from core.authority import is_owner
        if not is_owner(message):
            bot.reply_to(message, "⛔ OWNER only", parse_mode=None)
            return
        parts = str(getattr(message, "text", "") or "").split(maxsplit=2)
        if len(parts) < 2 or not re.fullmatch(r"BUGTASK_\d{6}", parts[1]):
            bot.reply_to(message, "שימוש: /close_bug_task <BUGTASK_ID> <resolution>", parse_mode=None)
            return
        task_id = parts[1]
        resolution = parts[2].strip()[:500] if len(parts) > 2 else ""
        closed_by = str(getattr(getattr(message, "from_user", None), "id", "") or "")

        def mutate(db):
            tasks = db.setdefault("bug_triage_tasks", [])
            if not isinstance(tasks, list):
                return {"ok": False, "reason": "invalid_store"}
            task = next((item for item in tasks if isinstance(item, dict) and item.get("id") == task_id), None)
            if task is None:
                return {"ok": False, "reason": "not_found"}
            if str(task.get("status") or "").upper() == "CLOSED":
                return {"ok": False, "reason": "already_closed"}
            now = datetime.now(timezone.utc).isoformat()
            task["status"] = "CLOSED"
            task["closed_at"] = now
            task["closed_by"] = closed_by
            task["resolution"] = resolution
            task["updated_at"] = now
            report_ids = {str(item) for item in (task.get("report_ids") or [])}
            feedback = db.get("user_feedback", [])
            if isinstance(feedback, list):
                for item in feedback:
                    if isinstance(item, dict) and str(item.get("id")) in report_ids:
                        item["status"] = "RESOLVED"
                        item["resolved_at"] = now
                        item["resolved_by"] = closed_by
                        if resolution:
                            item["resolution"] = resolution
            return {"ok": True, "task": task}

        result = state_manager.atomic_update(mutate)
        reason = result.get("reason")
        if result.get("ok"):
            bot.reply_to(message, f"✅ נסגרה המשימה {task_id}; הדיווחים המקושרים סומנו RESOLVED.", parse_mode=None)
        elif reason == "not_found":
            bot.reply_to(message, f"❌ המשימה {task_id} לא נמצאה.", parse_mode=None)
        elif reason == "already_closed":
            bot.reply_to(message, f"ℹ️ המשימה {task_id} כבר סגורה.", parse_mode=None)
        else:
            bot.reply_to(message, "⛔ לא ניתן לסגור את המשימה בבטחה.", parse_mode=None)

    print("✅ opt-in bugreport/suggest handler registered")
