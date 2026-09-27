import os
import requests
from telebot import types

from core.authority import get_role, is_owner
from core.identity import OWNER_TELEGRAM_ID


def _lab_base_url():
    return str(
        os.getenv("SLH_CONTROL_PLANE_URL", "https://web-production-22f28.up.railway.app")
    ).rstrip("/")


def _lab_token():
    return str(os.getenv("SLH_DEVELOPER_LAB_TOKEN", "")).strip()


def _call(method, path, uid, payload=None):
    token = _lab_token()
    if not token:
        raise RuntimeError("DEVELOPER_LAB_TOKEN_MISSING")
    headers = {
        "X-SLH-Dev-Lab-Token": token,
        "X-SLH-Actor-UID": str(uid),
        "Content-Type": "application/json",
    }
    response = requests.request(
        method,
        _lab_base_url() + path,
        headers=headers,
        json=payload,
        timeout=20,
    )
    try:
        body = response.json()
    except Exception:
        body = {"error": response.text[:250]}
    if response.status_code >= 400:
        raise RuntimeError(
            str(body.get("error") or body.get("detail") or "LAB_REQUEST_FAILED")
        )
    return body


def register(bot):
    @bot.message_handler(commands=["dev_read"])
    def dev_read(m):
        role = get_role(m.from_user.id)
        if role not in {"DEVELOPER", "ADMIN", "OWNER"}:
            bot.reply_to(m, "⛔ Developer Access required.")
            return
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /dev_read <path>")
            return
        try:
            result = _call(
                "GET",
                "/api/dev/lab/file?path=" + requests.utils.quote(parts[1].strip(), safe="/._-"),
                m.from_user.id,
            )
            content = str(result.get("content") or "")
            if result.get("truncated"):
                content += "\n… truncated at 12000 bytes"
            bot.reply_to(
                m,
                f"📄 {result.get('path')}\n\n{content}"[:3900],
            )
        except Exception as exc:
            bot.reply_to(m, f"❌ Developer read: {type(exc).__name__}: {str(exc)[:200]}")

    @bot.message_handler(commands=["dev_write"])
    def dev_write(m):
        role = get_role(m.from_user.id)
        if role not in {"DEVELOPER", "ADMIN", "OWNER"}:
            bot.reply_to(m, "⛔ Developer Access required.")
            return

        raw = m.text or ""
        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(
                m,
                "Usage:\n/dev_write <path> <summary>\n"
                "then put the complete UTF-8 file content after the command.\n"
                "Example:\n/dev_write handlers/example.py Add example handler\n"
                "print('hello')",
            )
            return

        path = parts[1].strip()
        rest = parts[2]
        lines = rest.splitlines()
        summary = lines[0].strip()[:240] if lines else "Developer code change"
        content = "\n".join(lines[1:]) if len(lines) > 1 else ""

        if not content.strip():
            bot.reply_to(
                m,
                "❌ חסר תוכן קובץ. השורה הראשונה אחרי הנתיב היא Summary, "
                "וכל השורות שאחריה הן תוכן הקובץ.",
            )
            return

        try:
            result = _call(
                "POST",
                "/api/dev/lab/propose",
                m.from_user.id,
                {"path": path, "summary": summary, "content": content},
            )
            request_id = result["id"]
            if is_owner(m.from_user.id):
                bot.reply_to(
                    m,
                    f"🧪 Developer Lab proposal created\n"
                    f"ID: {request_id}\n"
                    f"Path: {path}\n"
                    "As OWNER, approve it with /dev_lab_approve <id>.",
                )
                return

            owner_markup = types.InlineKeyboardMarkup()
            owner_markup.add(
                types.InlineKeyboardButton(
                    "✅ APPROVE → GitHub PR",
                    callback_data=f"devlab_approve_{request_id}",
                ),
                types.InlineKeyboardButton(
                    "❌ REJECT",
                    callback_data=f"devlab_reject_{request_id}",
                ),
            )
            bot.send_message(
                OWNER_TELEGRAM_ID,
                "🧪 Developer Lab — approval required\n\n"
                f"Developer: {m.from_user.id}\n"
                f"Path: {path}\n"
                f"Summary: {summary}\n"
                f"Request: {request_id}",
                reply_markup=owner_markup,
            )
            bot.reply_to(
                m,
                f"📨 שינוי נשמר כ־proposal {request_id}.\n"
                "ממתין לאישור OWNER; אין שינוי ב-production.",
            )
        except Exception as exc:
            bot.reply_to(
                m,
                f"❌ Developer Lab: {type(exc).__name__}: {str(exc)[:250]}",
            )

    @bot.message_handler(commands=["dev_lab_requests"])
    def dev_lab_requests(m):
        role = get_role(m.from_user.id)
        if role not in {"DEVELOPER", "ADMIN", "OWNER"}:
            bot.reply_to(m, "⛔ Developer Access required.")
            return
        try:
            result = _call("GET", "/api/dev/lab/requests", m.from_user.id)
            rows = result.get("requests", [])
            if not rows:
                bot.reply_to(m, "📭 אין Developer Lab proposals ממתינים.")
                return
            text = "🧪 Developer Lab — pending\n\n"
            for row in rows[:20]:
                text += (
                    f"• {row.get('id')} · UID {row.get('uid')} · "
                    f"{row.get('path')} · {row.get('summary')}\n"
                )
            bot.reply_to(m, text[:3900])
        except Exception as exc:
            bot.reply_to(m, f"❌ Developer Lab: {type(exc).__name__}")

    @bot.message_handler(commands=["dev_lab_status"])
    def dev_lab_status(m):
        role = get_role(m.from_user.id)
        if role not in {"DEVELOPER", "ADMIN", "OWNER"}:
            bot.reply_to(m, "⛔ Developer Access required.")
            return
        parts = (m.text or "").split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /dev_lab_status <request_id>")
            return
        try:
            result = _call(
                "GET",
                "/api/dev/lab/status/" + parts[1].strip(),
                m.from_user.id,
            )
            bot.reply_to(
                m,
                "🧪 Developer Lab\n\n"
                f"ID: {result.get('id')}\n"
                f"Status: {result.get('status')}\n"
                f"Path: {result.get('path')}\n"
                f"Branch: {result.get('branch') or '—'}\n"
                f"PR: #{result.get('pr_number') or '—'}\n"
                f"{result.get('pr_url') or ''}",
            )
        except Exception as exc:
            bot.reply_to(m, f"❌ Developer Lab: {type(exc).__name__}")

    @bot.message_handler(commands=["dev_lab_approve"])
    def dev_lab_approve(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = (m.text or "").split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /dev_lab_approve <request_id>")
            return
        try:
            result = _call(
                "POST",
                "/api/dev/lab/approve/" + parts[1].strip(),
                m.from_user.id,
            )
            bot.reply_to(
                m,
                "✅ Developer Lab approved\n"
                f"PR #{result.get('pr_number')}\n"
                f"{result.get('pr_url') or ''}",
            )
        except Exception as exc:
            bot.reply_to(
                m,
                f"❌ Approval failed: {type(exc).__name__}: {str(exc)[:200]}",
            )

    @bot.message_handler(commands=["dev_lab_reject"])
    def dev_lab_reject(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = (m.text or "").split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /dev_lab_reject <request_id>")
            return
        try:
            result = _call(
                "POST",
                "/api/dev/lab/reject/" + parts[1].strip(),
                m.from_user.id,
            )
            bot.reply_to(m, f"❌ Proposal {result.get('id')} rejected.")
        except Exception as exc:
            bot.reply_to(m, f"❌ Reject failed: {type(exc).__name__}")

    @bot.message_handler(commands=["dev_ci"])
    def dev_ci(m):
        role = get_role(m.from_user.id)
        if role not in {"DEVELOPER", "ADMIN", "OWNER"}:
            bot.reply_to(m, "⛔ Developer Access required.")
            return
        parts = (m.text or "").split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /dev_ci <request_id>")
            return
        try:
            result = _call(
                "GET",
                "/api/dev/lab/ci/" + parts[1].strip(),
                m.from_user.id,
            )
            checks = result.get("ci_checks", [])
            lines = [
                "🧪 GitHub CI",
                f"PR #{result.get('pr_number')}",
                f"Checks: {result.get('ci_total', 0)}",
            ]
            for item in checks[:20]:
                lines.append(
                    f"• {item.get('name')}: {item.get('status')} / {item.get('conclusion')}"
                )
            bot.reply_to(m, "\n".join(lines)[:3900])
        except Exception as exc:
            bot.reply_to(m, f"❌ CI lookup failed: {type(exc).__name__}")

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith(("devlab_approve_", "devlab_reject_"))
    )
    def devlab_callback(call):
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ OWNER only")
            return
        request_id = call.data.rsplit("_", 1)[-1]
        try:
            if call.data.startswith("devlab_approve_"):
                result = _call(
                    "POST",
                    "/api/dev/lab/approve/" + request_id,
                    call.from_user.id,
                )
                bot.answer_callback_query(call.id, "✅ PR created")
                bot.send_message(
                    call.from_user.id,
                    "✅ Developer Lab approved\n"
                    f"PR #{result.get('pr_number')}\n"
                    f"{result.get('pr_url') or ''}",
                )
            else:
                result = _call(
                    "POST",
                    "/api/dev/lab/reject/" + request_id,
                    call.from_user.id,
                )
                bot.answer_callback_query(call.id, "❌ rejected")
                bot.send_message(
                    call.from_user.id,
                    f"❌ Proposal {result.get('id')} rejected.",
                )
        except Exception as exc:
            bot.answer_callback_query(call.id, "❌ failed")
            bot.send_message(
                call.from_user.id,
                f"❌ Developer Lab: {type(exc).__name__}: {str(exc)[:250]}",
            )

    print("✅ developer_lab loaded")
