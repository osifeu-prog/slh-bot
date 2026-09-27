import os
import time
import requests
from telebot import types

from core.authority import get_role, is_owner
from core.developer_lab import can_propose_path
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

    write_sessions = {}

    def _expire_write_sessions():
        now = time.time()
        for uid, session in list(write_sessions.items()):
            if float(session.get("expires_at", 0)) <= now:
                write_sessions.pop(uid, None)

    def _validate_write_path(path):
        try:
            if not can_propose_path(path):
                return False, f"⛔ הנתיב {path} הוא read-only / protected ב-Developer Lab."
        except (TypeError, ValueError, PermissionError):
            return False, "⛔ נתיב לא תקין ל-Developer Lab."
        return True, ""


    def _start_write_session(m, path, summary):
        allowed, error_message = _validate_write_path(path)
        if not allowed:
            bot.reply_to(
                m,
                error_message
                + "\nלקריאה השתמש ב-/dev_read. שינויים ב-store/, state/, authority ונתיבי settlement נשארים מחוץ ל-Developer Lab.",
            )
            return False

        write_sessions[str(m.from_user.id)] = {
            "path": path,
            "summary": summary,
            "expires_at": time.time() + 600,
        }
        markup = types.ForceReply(selective=True)
        bot.reply_to(
            m,
            "🧪 Developer Lab — send the complete file content in your next message "
            "or as a document reply.\n"
            f"Path: {path}\n"
            f"Summary: {summary}\n"
            "Session expires in 10 minutes.\n"
            "No production change occurs until OWNER approval.",
            reply_markup=markup,
        )

    def _submit_write_content(m, content):
        _expire_write_sessions()
        uid = str(m.from_user.id)
        session = write_sessions.get(uid)
        if not session:
            return False
        if str(get_role(uid)) not in {"DEVELOPER", "ADMIN", "OWNER"}:
            write_sessions.pop(uid, None)
            return False
        try:
            result = _call(
                "POST",
                "/api/dev/lab/propose",
                uid,
                {
                    "path": session["path"],
                    "summary": session["summary"],
                    "content": content,
                    "chat_id": str(m.chat.id),
                },
            )
            write_sessions.pop(uid, None)
            request_id = result["id"]
            if is_owner(uid):
                bot.reply_to(
                    m,
                    f"🧪 Developer Lab proposal created\n"
                    f"ID: {request_id}\n"
                    f"Path: {session['path']}\n"
                    "As OWNER, approve it with /dev_lab_approve <id>.",
                )
                return True

            owner_markup = types.InlineKeyboardMarkup()
            owner_markup.row(
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
                f"Developer: {uid}\n"
                f"Path: {session['path']}\n"
                f"Summary: {session['summary']}\n"
                f"Request: {request_id}",
                reply_markup=owner_markup,
            )
            bot.reply_to(
                m,
                f"📨 שינוי נשמר כ־proposal {request_id}.\n"
                "ממתין לאישור OWNER; אין שינוי ב-production.",
            )
            return True
        except Exception as exc:
            bot.reply_to(
                m,
                f"❌ Developer Lab: {type(exc).__name__}: {str(exc)[:250]}",
            )
            return True

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
                "Usage:\n"
                "/dev_write <path> <summary>\n"
                "Then reply to the bot with the complete file content, "
                "or attach the file as a document reply.",
            )
            return

        path = parts[1].strip()
        rest = parts[2]
        lines = rest.splitlines()
        summary = lines[0].strip()[:240] if lines else "Developer code change"
        inline_content = "\n".join(lines[1:]) if len(lines) > 1 else ""
        if inline_content.strip():
            allowed, error_message = _validate_write_path(path)
            if not allowed:
                bot.reply_to(
                    m,
                    error_message
                    + "\nלקריאה השתמש ב-/dev_read. שינויים ב-store/, state/, authority ונתיבי settlement נשארים מחוץ ל-Developer Lab.",
                )
                return
            write_sessions[str(m.from_user.id)] = {
                "path": path,
                "summary": summary,
                "expires_at": time.time() + 600,
            }
            _submit_write_content(m, inline_content)
            return

        _start_write_session(m, path, summary)

    @bot.message_handler(
        func=lambda m: bool(
            m.reply_to_message
            and m.from_user
            and str(m.from_user.id) in write_sessions
            and not (m.text or "").lstrip().startswith("/")
        ),
        content_types=["text"],
    )
    def dev_write_reply(m):
        _submit_write_content(m, m.text or "")
    
    @bot.message_handler(
        func=lambda m: bool(
            m.reply_to_message
            and m.from_user
            and str(m.from_user.id) in write_sessions
        ),
        content_types=["document"],
    )
    def dev_write_document(m):
        try:
            _expire_write_sessions()
            uid = str(m.from_user.id)
            session = write_sessions.get(uid)
            if not session:
                return
            file_info = bot.get_file(m.document.file_id)
            content = bot.download_file(file_info.file_path)
            if len(content) > 24000:
                bot.reply_to(m, "❌ File too large. Maximum Developer Lab payload is 24 KB.")
                return
            _submit_write_content(m, content.decode("utf-8", errors="replace"))
        except Exception as exc:
            bot.reply_to(m, f"❌ Developer Lab document: {type(exc).__name__}: {str(exc)[:200]}")

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

    @bot.message_handler(commands=["dev_lab_preview"])
    def dev_lab_preview(m):
        role = get_role(m.from_user.id)
        if role not in {"DEVELOPER", "ADMIN", "OWNER"}:
            bot.reply_to(m, "⛔ Developer Access required.")
            return
        parts = (m.text or "").split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /dev_lab_preview <request_id>")
            return
        try:
            result = _call(
                "GET",
                "/api/dev/lab/preview/" + parts[1].strip(),
                m.from_user.id,
            )
            content = str(result.get("content") or "")
            if result.get("truncated"):
                content += "\n… truncated at 3500 chars"
            bot.reply_to(
                m,
                f"🧪 Proposal {result.get('id')}\n"
                f"Path: {result.get('path')}\n"
                f"Summary: {result.get('summary')}\n"
                f"SHA256: {result.get('content_sha256')}\n\n"
                f"{content}"[:3900],
            )
        except Exception as exc:
            bot.reply_to(m, f"❌ Preview failed: {type(exc).__name__}: {str(exc)[:200]}")

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
            approval_message = (
                "✅ Developer Lab approved\n"
                f"PR #{result.get('pr_number')}\n"
                f"{result.get('pr_url') or ''}"
            )
            bot.reply_to(m, approval_message)

            developer_uid = str(result.get("uid") or "")
            developer_chat_id = str(result.get("chat_id") or "")
            notice = (
                "✅ Your Developer Lab proposal was approved by OWNER.\n"
                f"Proposal: {result.get('id')}\n"
                f"PR #{result.get('pr_number')}\n"
                f"{result.get('pr_url') or ''}\n"
                "Production deploy is not automatic; CI/merge remain separate."
            )

            delivered = False
            delivery_error = ""
            direct_target = developer_chat_id or developer_uid
            if direct_target and direct_target != str(m.chat.id):
                try:
                    bot.send_message(direct_target, notice)
                    delivered = True
                except Exception as exc:
                    delivery_error = f"{type(exc).__name__}: {str(exc)[:180]}"

            if not delivered and str(m.chat.id) != developer_uid:
                try:
                    bot.send_message(
                        m.chat.id,
                        "📩 Developer Lab approval notification\n"
                        f"Developer: {developer_uid or 'unknown'}\n"
                        f"PR #{result.get('pr_number')}\n"
                        f"{result.get('pr_url') or ''}",
                    )
                    delivered = True
                except Exception as exc:
                    delivery_error = f"{type(exc).__name__}: {str(exc)[:180]}"

            if delivered:
                bot.reply_to(
                    m,
                    "📩 אישור נמסר למפתח בהצלחה. "
                    f"PR #{result.get('pr_number')}.",
                )
            else:
                bot.reply_to(
                    m,
                    "⚠️ ה־PR אושר אבל Telegram לא מסר את ההודעה למפתח.\n"
                    f"Developer UID: {developer_uid or 'unknown'}\n"
                    f"Delivery error: {delivery_error or 'UNKNOWN'}\n"
                    "ה־PR קיים וניתן לפתוח אותו ישירות.",
                )
        except Exception as exc:
            bot.reply_to(
                m,
                f"❌ Approval failed: {type(exc).__name__}: {str(exc)[:200]}",
            )

    @bot.message_handler(commands=["dev_lab_notify"])
    def dev_lab_notify(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = (m.text or "").split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /dev_lab_notify <request_id>")
            return
        request_id = parts[1].strip()
        try:
            result = _call(
                "GET",
                "/api/dev/lab/status/" + request_id,
                m.from_user.id,
            )
            developer_uid = str(result.get("uid") or "")
            if not developer_uid:
                raise RuntimeError("DEVELOPER_UID_MISSING")
            status = str(result.get("status") or "")
            if status != "pr_open":
                raise RuntimeError(f"REQUEST_NOT_PR_OPEN:{status}")
            developer_chat_id = str(result.get("chat_id") or "")
            notice = (
                "✅ Your Developer Lab proposal was approved by OWNER.\n"
                f"Proposal: {result.get('id')}\n"
                f"PR #{result.get('pr_number')}\n"
                f"{result.get('pr_url') or ''}\n"
                "Production deploy is not automatic; CI/merge remain separate."
            )
            delivered = False
            direct_target = developer_chat_id or developer_uid
            if direct_target and direct_target != str(m.chat.id):
                try:
                    bot.send_message(direct_target, notice)
                    delivered = True
                except Exception:
                    delivered = False
            if not delivered and str(m.chat.id) != developer_uid:
                bot.send_message(
                    m.chat.id,
                    "📩 Developer Lab approval notification\n"
                    f"Developer: {developer_uid}\n"
                    f"PR #{result.get('pr_number')}\n"
                    f"{result.get('pr_url') or ''}",
                )
                delivered = True
            bot.reply_to(
                m,
                f"📩 Approval notification sent to Developer {developer_uid} "
                f"for PR #{result.get('pr_number')}.",
            )
        except Exception as exc:
            bot.reply_to(
                m,
                f"❌ Developer notification failed: {type(exc).__name__}: {str(exc)[:200]}",
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
            for item in checks[:12]:
                lines.append(
                    f"• {item.get('name')}: {item.get('status')} / {item.get('conclusion')}"
                )

            evidence = result.get("workflow_evidence") or []
            if evidence:
                lines.append("")
                lines.append("🔎 Runner diagnostics:")
                for run in evidence[:8]:
                    if run.get("error"):
                        lines.append(f"• diagnostics error: {run.get('error')}")
                        continue
                    lines.append(
                        f"• {run.get('workflow')}: run {run.get('run_id')} "
                        f"{run.get('status')}/{run.get('conclusion')}"
                    )
                    for job in (run.get("jobs") or [])[:4]:
                        lines.append(
                            f"  ↳ {job.get('job')}: "
                            f"{job.get('status')}/{job.get('conclusion')} "
                            f"runner={job.get('runner_id') or 'none'} "
                            f"steps={job.get('steps_count') if job.get('steps_count') is not None else 'none'}"
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
                developer_uid = str(result.get("uid") or "")
                if developer_uid and developer_uid != str(call.from_user.id):
                    bot.send_message(
                        developer_uid,
                        "✅ Your Developer Lab proposal was approved by OWNER.\n"
                        f"PR #{result.get('pr_number')}\n"
                        f"{result.get('pr_url') or ''}\n"
                        "Production deploy is not automatic; CI/merge remain separate.",
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
