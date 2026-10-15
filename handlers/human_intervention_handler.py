"""Owner-only private interface for fail-closed system-action approvals."""
from core.authority import is_owner
from core import human_intervention as policy
from core.exec_policy import redact_secrets, run_gated


def _authorized_private(message):
    chat = getattr(message, "chat", None)
    user = getattr(message, "from_user", None)
    return (
        chat is not None
        and getattr(chat, "type", None) == "private"
        and user is not None
        and is_owner(getattr(user, "id", None))
    )


def _status_text():
    status = policy.get_status()
    lines = [
        "🛡 HUMAN INTERVENTION — READ STATUS",
        f"Policy source: {status['policy_source']}",
        f"Policy store available: {status['policy_available']}",
        f"Execution approval required: {status['settings']['action_execution']}",
        f"Completion approval required: {status['settings']['action_completion']}",
        f"Audit events: {status['audit_events']}",
        "",
        "Pending / unresolved requests:",
    ]
    pending = status.get("pending", [])
    if pending:
        lines.extend(
            f"• {item['id']} — {item['status']} — {item.get('source') or 'unknown'}"
            for item in pending[:15]
        )
    else:
        lines.append("• none")
    lines.extend([
        "",
        "Commands:",
        "/intervention show <ID>",
        "/intervention approve <ID>",
        "/intervention deny <ID>",
        "/intervention complete <ID>",
        "/intervention set action_execution on|off",
        "/intervention set action_completion on|off",
        "/intervention confirm_disable <ID>",
    ])
    return "\n".join(lines)


def register(bot, context=None):
    @bot.message_handler(commands=["intervention"])
    def intervention_command(message):
        if not _authorized_private(message):
            bot.reply_to(
                message,
                "⛔ הפעולה זמינה לבעלים בלבד ובצ'אט פרטי עם הבוט.",
            )
            return

        parts = (message.text or "").split()
        if len(parts) == 1 or (len(parts) == 2 and parts[1].lower() in {"status", "show_status"}):
            bot.reply_to(message, _status_text())
            return

        subcommand = parts[1].lower()

        if subcommand == "show":
            if len(parts) != 3:
                bot.reply_to(message, "שימוש: /intervention show <ID>")
                return
            record = policy.get_request(parts[2])
            if not record:
                bot.reply_to(message, "❌ בקשת הפעולה לא נמצאה.")
                return
            command = str(record.get("command") or "")
            if not command:
                command = "(פקודה הוסרה לאחר סיום/דחייה)"
            command = redact_secrets(command)
            if len(command) > 2800:
                command = command[:2800] + "\n... truncated"
            bot.reply_to(
                message,
                "🔎 SYSTEM ACTION REQUEST — READ ONLY\n"
                f"ID: {record.get('id')}\n"
                f"Status: {record.get('status')}\n"
                f"Source: {record.get('source') or 'unknown'}\n"
                f"Requested by: {record.get('requested_by')}\n"
                f"Created: {record.get('created_at')}\n"
                f"Expires: {record.get('expires_at')}\n"
                f"Command SHA256: {record.get('command_sha256')}\n\n"
                "Command preview (redacted best-effort):\n"
                f"{command}\n\n"
                "No command was executed by this display.",
            )
            return

        if subcommand == "set":
            if len(parts) != 4:
                bot.reply_to(
                    message,
                    "שימוש: /intervention set <action_execution|action_completion> <on|off>",
                )
                return
            setting, value = parts[2], parts[3].lower()
            if setting not in policy.VALID_SETTINGS or value not in {"on", "off"}:
                bot.reply_to(message, "❌ הגדרה או ערך לא תקינים.")
                return
            try:
                if value == "on":
                    result = policy.enable_setting(message.from_user.id, setting)
                    bot.reply_to(
                        message,
                        f"✅ {setting}=ON — יידרש אישור אנושי. "
                        f"אירוע ביקורת נרשם (ID {result['request_id']}).",
                    )
                else:
                    result = policy.request_setting_disable(message.from_user.id, setting)
                    if result.get("already_disabled"):
                        bot.reply_to(message, f"ℹ️ {setting} כבר כבוי.")
                    else:
                        bot.reply_to(
                            message,
                            f"⚠️ {setting} יישאר ON עד לאישור מפורש.\n"
                            f"לא בוצע שינוי בהגדרה.\n"
                            f"לאישור הכיבוי, שלח בתוך 5 דקות:\n"
                            f"/intervention confirm_disable {result['request_id']}",
                        )
            except Exception as exc:
                bot.reply_to(message, f"❌ שינוי ההגדרה נכשל בבטחה: {type(exc).__name__}")
            return

        if subcommand == "confirm_disable":
            if len(parts) != 3:
                bot.reply_to(message, "שימוש: /intervention confirm_disable <ID>")
                return
            result = policy.confirm_setting_disable(parts[2], message.from_user.id)
            if result.get("ok"):
                bot.reply_to(
                    message,
                    f"⚠️ {result['setting']}=OFF — הכיבוי אושר ונרשם ביומן הביקורת.",
                )
            else:
                bot.reply_to(message, f"❌ הכיבוי לא הוחל: {result.get('error', 'UNKNOWN')}")
            return

        if subcommand == "approve":
            if len(parts) != 3:
                bot.reply_to(message, "שימוש: /intervention approve <ID>")
                return
            request_id = parts[2]
            record = policy.get_request(request_id)
            if not record or record.get("status") != "pending_execution":
                bot.reply_to(message, "❌ הבקשה אינה ממתינה לאישור ביצוע.")
                return
            decision = policy.approve_execution(request_id, message.from_user.id)
            if not decision.get("ok"):
                bot.reply_to(message, f"❌ האישור נדחה: {decision.get('error', 'UNKNOWN')}")
                return
            if record.get("kind") == "registered_action":
                claim = policy.claim_execution(
                    request_id, message.from_user.id, str(record.get("command") or "")
                )
                if not claim.get("ok"):
                    bot.reply_to(message, f"❌ הפעולה לא התחילה: {claim.get('error', 'UNKNOWN')}")
                    return
                try:
                    action_key = record.get("action_key")
                    params = record.get("parameters") if isinstance(record.get("parameters"), dict) else {}
                    if action_key == "alpha_open":
                        from core.alpha_control_plane import open_alpha
                        result = open_alpha(message.from_user.id)
                        output = "Alpha state: " + str(result.get("status", "OPEN"))
                    elif action_key == "railway_up":
                        from core.railway_control import canonical_up
                        commit_sha = params.get("commit_sha")
                        result = canonical_up(commit_sha=commit_sha) if commit_sha else canonical_up()
                        output = (
                            "Railway deploy triggered.\n"
                            f"Project: {result.get('project')}\n"
                            f"Service: {result.get('service')}\n"
                            f"Commit: {str(result.get('commit') or 'unknown')[:12]}\n"
                            f"Deployment: {str(result.get('deployment_id') or 'unknown')}"
                        )
                    else:
                        raise ValueError("UNREGISTERED_ACTION")
                    lifecycle = policy.record_execution_result(
                        request_id, message.from_user.id, success=True,
                        result_code="registered_action_success",
                    )
                    if not lifecycle.get("ok"):
                        bot.reply_to(message, f"⚠️ הפעולה הושלמה אך הרישום נכשל. ID: {request_id}")
                        return
                    if lifecycle.get("status") == "executed_pending_completion":
                        output += f"\n\n⏸ נדרש אישור סיום: /intervention complete {request_id}"
                    bot.reply_to(message, f"✅ פעולה מאושרת\nID: {request_id}\n{output}"[:3900])
                except Exception as exc:
                    try:
                        policy.record_execution_result(
                            request_id, message.from_user.id, success=False,
                            result_code="registered_action_failed:" + type(exc).__name__,
                        )
                    except Exception:
                        pass
                    bot.reply_to(
                        message,
                        "❌ הפעולה נכשלה או נחסמה בידי ה-gate הפנימי. "
                        "היתכנות side effects לא הונחה; יש לבדוק את מצב הפעולה לפני retry. "
                        f"ID: {request_id} · {type(exc).__name__}",
                    )
                return

            command = str(record.get("command") or "")
            ok, output = run_gated(
                message.from_user.id,
                command,
                source="human_intervention_approved",
                intervention_request_id=request_id,
            )
            if ok:
                bot.reply_to(message, f"✅ תוצאת הביצוע\nID: {request_id}\n{output}"[:3900])
            else:
                bot.reply_to(message, f"⛔ הביצוע נחסם או נכשל\nID: {request_id}\n{output}"[:3900])
            return

        if subcommand == "deny":
            if len(parts) != 3:
                bot.reply_to(message, "שימוש: /intervention deny <ID>")
                return
            result = policy.deny_action(parts[2], message.from_user.id)
            if result.get("ok"):
                bot.reply_to(
                    message,
                    f"✅ הבקשה נדחתה ונרשמה.\nStatus: {result['status']}\n"
                    "דחיית completion אינה מבטלת פעולה שכבר בוצעה.",
                )
            else:
                bot.reply_to(message, f"❌ הדחייה לא הוחלה: {result.get('error', 'UNKNOWN')}")
            return

        if subcommand == "complete":
            if len(parts) != 3:
                bot.reply_to(message, "שימוש: /intervention complete <ID>")
                return
            result = policy.complete_action(parts[2], message.from_user.id)
            if result.get("ok"):
                bot.reply_to(message, f"✅ הפעולה סומנה כהושלמה ונרשמה. ID: {parts[2]}")
            else:
                bot.reply_to(message, f"❌ הסיום לא אושר: {result.get('error', 'UNKNOWN')}")
            return

        bot.reply_to(
            message,
            "פקודה לא מוכרת. שלח /intervention להצגת מצב והתחביר הנתמך.",
        )

    print("✅ human intervention handler registered")
