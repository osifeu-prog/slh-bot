"""Owner-only UI and dispatch for persisted approval gates at action authorities."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from telebot import types

from core.authority import is_owner
from core.identity import OWNER_TELEGRAM_ID
from core import human_intervention as hi

ACTION_LABELS = {
    "mission_execute": "ביצוע משימה / הפעלת סוכן",
    "mission_complete": "אישור השלמת משימה",
    "task_complete": "השלמת משימה ותגמול",
}


def _private_owner(obj) -> bool:
    user = getattr(obj, "from_user", None)
    message = getattr(obj, "message", None) or obj
    chat = getattr(message, "chat", None)
    uid = str(getattr(user, "id", "") or "")
    chat_id = str(getattr(chat, "id", "") or "")
    chat_type = str(getattr(chat, "type", "") or "").lower()
    return bool(uid and is_owner(uid) and chat_type == "private"
                and chat_id == str(OWNER_TELEGRAM_ID))


def _settings_text() -> str:
    snapshot = hi.get_settings()
    required = snapshot.get("required", {})
    configured = snapshot.get("configured", {})
    lines = [
        "🛡️ SLH — Human Intervention",
        "מדיניות אישורים נשמרת ב־DB הקנוני.",
        "",
    ]
    for name, label in (
        ("action_execution", "לפני ביצוע פעולת מערכת"),
        ("action_completion", "לפני סיום / commit / תגמול"),
    ):
        state = "אישור OWNER נדרש" if required.get(name, True) else "האישור מנוטרל באישור OWNER"
        origin = "מוגדר" if configured.get(name, False) else "ברירת מחדל fail-closed"
        lines.append(f"• {name} — {label}: {state} [{origin}]")
    lines.extend([
        "",
        "פקודות:",
        "/config status",
        "/config add action_execution",
        "/config add action_completion",
        "/config set <action_execution|action_completion> <on|off>",
        "/config confirm <confirmation_id> — אישור שני לנטרול",
        "/approve_action <request_id>",
        "/reject_action <request_id>",
        "",
        "מימוש כרגע: mission_execute, mission_complete, task_complete.",
        "פעולות אחרות אינן נעשות מאושרות מכוח הגדרות אלה; unknown actions נשארות חסומות.",
    ])
    return "\n".join(lines)


def notify_approval_request(bot, request_id: str) -> bool:
    req = hi.get_request(str(request_id))
    if not req or req.get("status") != "pending":
        return False
    action = str(req.get("action", ""))
    label = ACTION_LABELS.get(action, action)
    try:
        expiry = datetime.fromtimestamp(float(req.get("expires_at")), timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        expiry = "לא זמין"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ אשר ובצע", callback_data=f"hi:a:{request_id}"),
        types.InlineKeyboardButton("⛔ דחה", callback_data=f"hi:r:{request_id}"),
    )
    message = (
        "🛡️ נדרש אישור אנושי — SLH OS\n"
        f"פעולה: {label} ({action})\n"
        f"יעד: {req.get('resource_id')}\n"
        f"מבקש UID: {req.get('requester_id')}\n"
        f"מזהה: {request_id}\n"
        f"תוקף עד: {expiry}\n\n"
        "האישור חד־פעמי, קשור לפעולה וליעד, ופג אחרי 30 דקות."
    )
    try:
        bot.send_message(OWNER_TELEGRAM_ID, message, reply_markup=markup)
        return True
    except Exception as exc:
        print("[HUMAN_INTERVENTION] owner notification failed:", type(exc).__name__)
        return False


def _notify_requester(bot, req, text: str) -> None:
    requester = str(req.get("requester_id") or "")
    chat_id = str(req.get("requester_chat_id") or "")
    if requester and chat_id == requester and requester != str(OWNER_TELEGRAM_ID):
        try:
            bot.send_message(int(chat_id), text[:3500])
        except Exception as exc:
            print("[HUMAN_INTERVENTION] requester notification failed:", type(exc).__name__)


def _complete_mission(mission_id: str, requester_uid: str, requester_chat_id=None,
                      human_approval_id=None) -> dict:
    from core.mission_lifecycle import MissionLifecycleService
    from core.mission_state import MissionStateNormalizer
    from core.mission_reward_service import issue_mission_reward

    lifecycle = MissionLifecycleService(".")
    try:
        result = lifecycle.complete_mission(
            mission_id=mission_id,
            requester_uid=requester_uid,
            requester_chat_id=requester_chat_id,
            human_approval_id=human_approval_id,
        )
    except Exception as exc:
        if human_approval_id:
            hi.finish_request(human_approval_id, success=False,
                              detail="mission completion exception: " + type(exc).__name__)
        return {"status": "blocked", "reason": type(exc).__name__}
    if result.get("status") != "completed":
        if human_approval_id:
            hi.finish_request(
                human_approval_id,
                success=False,
                detail="mission completion blocked: " + str(result.get("reason", result.get("status"))),
            )
        return result
    board, _manifest = lifecycle.load_state()
    mission = lifecycle.find_mission(board, mission_id)
    if mission is None or MissionStateNormalizer.normalize(mission.get("status")) != "completed":
        if human_approval_id:
            hi.finish_request(human_approval_id, success=False, detail="completed state not verified")
        return {"status": "blocked", "reason": "completed_state_not_verified"}
    reward = issue_mission_reward(mission, mission_id=mission_id)
    detail = "mission completed; reward=" + str(reward.get("status"))
    if human_approval_id:
        hi.finish_request(human_approval_id, success=True, detail=detail)
    else:
        audit = hi.record_action_event(
            "action_completed", actor_id=requester_uid, action="mission_complete",
            resource_id=mission_id, detail=detail,
        )
        if audit.get("status") != "recorded":
            return {"status": "blocked", "reason": "action_audit_write_failed",
                    "completion": result, "reward": reward}
    return {"status": "completed", "mission_id": mission_id,
            "completion": result, "reward": reward}


def _perform_body(bot, action: str, target: str, requester_uid: str,
                  requester_chat_id=None, human_approval_id=None) -> dict:
    if action == "mission_execute":
        from core.mission_runtime_authority import execute_mission_authority
        result = execute_mission_authority(
            mission_id=target,
            requester_uid=requester_uid,
            requester_chat_id=requester_chat_id,
            human_approval_id=human_approval_id,
        )
        if result.get("status") == "approval_required":
            return result
        if result.get("status") != "executed":
            return {"status": "blocked", "action": action, "details": result}
        completion = _complete_mission(target, requester_uid, requester_chat_id)
        if completion.get("status") == "approval_required":
            return {
                "status": "executed_completion_pending_approval",
                "action": action,
                "mission_id": target,
                "completion_request_id": completion.get("request_id"),
                "execution": result,
            }
        return {
            "status": "executed_then_completed" if completion.get("status") == "completed"
                      else "executed_completion_blocked",
            "action": action, "execution": result, "completion": completion,
        }

    if action == "mission_complete":
        return _complete_mission(target, requester_uid, requester_chat_id,
                                 human_approval_id=human_approval_id)

    if action == "task_complete":
        from core.task_completion_service import complete_task
        try:
            return complete_task(
                uid=requester_uid,
                task_id=target,
                meta={"source": "human_intervention_gate", "telegram_user_id": requester_uid},
                requester_chat_id=requester_chat_id,
                human_approval_id=human_approval_id,
            )
        except Exception as exc:
            if human_approval_id:
                hi.finish_request(human_approval_id, success=False,
                                  detail="task completion exception: " + type(exc).__name__)
            return {"status": "blocked", "action": action,
                    "reason": type(exc).__name__, "details": str(exc)[:300]}

    return {"status": "blocked", "reason": "unknown_mutating_action"}


def _run_action(bot, action: str, target: str, requester_uid: str,
                requester_chat_id=None, approval_id=None) -> dict:
    req_before = hi.get_request(approval_id) if approval_id else None
    if approval_id and (not req_before or req_before.get("status") != "approved"):
        return {"status": "blocked", "reason": "approval_not_available"}
    try:
        result = _perform_body(
            bot, action, target, requester_uid, requester_chat_id,
            human_approval_id=approval_id,
        )
    except Exception as exc:
        if approval_id:
            hi.finish_request(approval_id, success=False,
                              detail="action handler exception: " + type(exc).__name__)
        return {"status": "blocked", "reason": type(exc).__name__, "details": str(exc)[:300]}

    pending_ids = []
    if result.get("status") == "approval_required" and result.get("request_id"):
        pending_ids.append(result["request_id"])
    if result.get("completion_request_id"):
        pending_ids.append(result["completion_request_id"])
    for request_id in dict.fromkeys(pending_ids):
        notified = notify_approval_request(bot, request_id)
        result["owner_notified"] = notified

    if approval_id and req_before:
        # Close an approved request even when a preflight blocks before the
        # authority consumes it. If a deeper authority already finished it,
        # this second finish is rejected as a replay and is intentionally ignored.
        succeeded = result.get("status") in {
            "completed", "executed", "executed_completion_pending_approval",
            "executed_then_completed",
        }
        hi.finish_request(
            approval_id,
            success=succeeded,
            detail=json.dumps(result, ensure_ascii=False, default=str)[:500],
        )
        _notify_requester(
            bot, req_before,
            "✅ הפעולה המורשית הסתיימה: " + str(result.get("status"))
            if result.get("status") in {"completed", "executed", "executed_completion_pending_approval",
                                        "executed_then_completed"}
            else "❌ הפעולה נחסמה או נכשלה: " + str(result.get("reason", result.get("status"))),
        )
    return result


def request_action(bot, *, action: str, resource_id: str, requester_uid: str,
                   requester_chat_id=None) -> dict:
    return _run_action(bot, action, resource_id, requester_uid, requester_chat_id)


def register(bot, context=None):
    @bot.message_handler(commands=["config"])
    def config_command(message):
        if not _private_owner(message):
            bot.reply_to(message, "⛔ הגדרות ההתערבות זמינות לבעלים בלבד, בצ'אט פרטי.")
            return
        args = (message.text or "").split()[1:]
        if not args or args[0].lower() == "status":
            bot.reply_to(message, _settings_text())
            return
        if len(args) == 2 and args[0].lower() == "add" and args[1] in hi.SETTING_NAMES:
            result = hi.set_required(args[1], required=True, actor_uid=str(message.from_user.id))
            bot.reply_to(message, _settings_text() + "\n\nתוצאה: " + str(result.get("status")))
            return
        if len(args) == 3 and args[0].lower() == "set" and args[1] in hi.SETTING_NAMES:
            value = args[2].lower()
            if value == "on":
                result = hi.set_required(args[1], required=True, actor_uid=str(message.from_user.id))
                bot.reply_to(message, json.dumps(result, ensure_ascii=False))
            elif value == "off":
                result = hi.propose_disable(args[1], actor_uid=str(message.from_user.id))
                bot.reply_to(message, "⚠️ נטרול מחייב אישור שני. " + json.dumps(result, ensure_ascii=False))
            else:
                bot.reply_to(message, "ערך חייב להיות on או off.")
            return
        if len(args) == 2 and args[0].lower() == "confirm":
            result = hi.confirm_disable(args[1], actor_uid=str(message.from_user.id))
            bot.reply_to(message, json.dumps(result, ensure_ascii=False))
            return
        bot.reply_to(message, "תחביר לא תקין. שלח /config status")

    def decide(message_or_call, request_id: str, choice: str, is_callback=False):
        if not _private_owner(message_or_call):
            if is_callback:
                bot.answer_callback_query(message_or_call.id, "OWNER private chat only", show_alert=True)
            else:
                bot.reply_to(message_or_call, "⛔ OWNER private chat only")
            return
        actor_uid = str(message_or_call.from_user.id)
        req_before = hi.get_request(request_id)
        decision = hi.decide_request(request_id, approver_uid=actor_uid, decision=choice)
        if decision.get("status") == "rejected":
            if is_callback:
                bot.answer_callback_query(message_or_call.id, "נדחה")
            if req_before:
                _notify_requester(bot, req_before, "⛔ בקשת הפעולה נדחתה על ידי OWNER.")
            return
        if decision.get("status") != "approved":
            msg = "הבקשה לא אושרה: " + str(decision.get("reason", decision.get("status")))
            if is_callback:
                bot.answer_callback_query(message_or_call.id, msg[:180], show_alert=True)
            else:
                bot.reply_to(message_or_call, msg)
            return
        if not req_before:
            if is_callback:
                bot.answer_callback_query(message_or_call.id, "בקשה לא נמצאה", show_alert=True)
            return
        output = _run_action(
            bot, str(req_before.get("action") or ""), str(req_before.get("resource_id") or ""),
            str(req_before.get("requester_id") or ""),
            req_before.get("requester_chat_id"), approval_id=request_id,
        )
        msg = "תוצאת האישור: " + str(output.get("status"))
        if is_callback:
            bot.answer_callback_query(message_or_call.id, msg[:180])
            bot.send_message(OWNER_TELEGRAM_ID, json.dumps(output, ensure_ascii=False, default=str)[:3500])
        else:
            bot.reply_to(message_or_call, json.dumps(output, ensure_ascii=False, default=str)[:3500])

    @bot.callback_query_handler(func=lambda call: str(getattr(call, "data", "") or "").startswith("hi:"))
    def human_intervention_callback(call):
        if not _private_owner(call):
            bot.answer_callback_query(call.id, "OWNER private chat only", show_alert=True)
            return
        parts = str(call.data).split(":")
        if len(parts) != 3 or parts[1] not in {"a", "r"}:
            bot.answer_callback_query(call.id, "בקשה לא תקינה", show_alert=True)
            return
        decide(call, parts[2], "approve" if parts[1] == "a" else "reject", is_callback=True)

    @bot.message_handler(commands=["approve_action"])
    def approve_action(message):
        parts = (message.text or "").split()
        if len(parts) != 2:
            bot.reply_to(message, "שימוש: /approve_action <request_id>")
            return
        decide(message, parts[1], "approve")

    @bot.message_handler(commands=["reject_action"])
    def reject_action(message):
        parts = (message.text or "").split()
        if len(parts) != 2:
            bot.reply_to(message, "שימוש: /reject_action <request_id>")
            return
        decide(message, parts[1], "reject")
