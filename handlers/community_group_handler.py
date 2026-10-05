"""Community group telemetry and owner-controlled group binding.

This module does not infer paid/free/Academy access. It records Telegram's
authoritative membership updates and lets the owner bind each known group to
an explicit role: free, vip, or academy.
"""

from __future__ import annotations

from datetime import datetime, timezone

import state_manager
from core.identity import OWNER_TELEGRAM_ID


VALID_ROLES = {"free", "vip", "academy"}


def _chat_snapshot(chat):
    return {
        "chat_id": str(chat.id),
        "type": getattr(chat, "type", None),
        "title": getattr(chat, "title", None),
        "username": getattr(chat, "username", None),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _record_membership(db, uid, chat, status, source="chat_member"):
    groups = db.setdefault("community_groups", {})
    memberships = db.setdefault("community_memberships", {})
    chat_id = str(chat.id)

    group = groups.setdefault(chat_id, {})
    group.update(_chat_snapshot(chat))
    group["last_event"] = source
    group["last_member_status"] = str(status)

    user_key = f"{uid}:{chat_id}"
    memberships[user_key] = {
        "uid": str(uid),
        "chat_id": chat_id,
        "status": str(status),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _bind_current_group(m, role):
    if role not in VALID_ROLES:
        raise ValueError("GROUP_ROLE_INVALID")
    if getattr(m.chat, "type", None) not in {"group", "supergroup"}:
        raise ValueError("GROUP_BIND_MUST_RUN_IN_GROUP")

    chat = m.chat

    def mutate(db):
        groups = db.setdefault("community_groups", {})
        snapshot = _chat_snapshot(chat)
        snapshot["role"] = role
        snapshot["bound_by"] = str(m.from_user.id)
        snapshot["bound_at"] = datetime.now(timezone.utc).isoformat()
        groups[str(chat.id)] = snapshot
        return snapshot

    return state_manager.atomic_update(mutate)


def register(bot):
    @bot.message_handler(commands=["group_bind"])
    def group_bind_cmd(m):
        if int(m.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(m, "⛔ OWNER only")
            return

        parts = (m.text or "").split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /group_bind <free|vip|academy>")
            return

        role = parts[1].strip().lower()
        try:
            group = _bind_current_group(m, role)
        except ValueError as exc:
            bot.reply_to(m, f"❌ {exc}")
            return

        bot.reply_to(
            m,
            "✅ קבוצה נקשרה למערכת.\n"
            f"Role: {group['role']}\n"
            f"Chat ID: {group['chat_id']}\n"
            f"Title: {group.get('title') or '-'}"
        )

    @bot.message_handler(commands=["group_status"])
    def group_status_cmd(m):
        if int(m.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(m, "⛔ OWNER only")
            return

        db = state_manager.load_db()
        groups = db.get("community_groups", {})
        memberships = db.get("community_memberships", {})

        role_counts = {role: 0 for role in sorted(VALID_ROLES)}
        for group in groups.values():
            role = str(group.get("role", "")).lower()
            if role in role_counts:
                role_counts[role] += 1

        bound_ids = []
        for chat_id, group in groups.items():
            role = group.get("role") or "unbound"
            title = group.get("title") or group.get("username") or chat_id
            bound_ids.append(f"{role}:{title}:{chat_id}")

        bot.reply_to(
            m,
            "👥 SLH Community\n"
            f"Groups: {len(groups)}\n"
            f"Bound free/vip/academy: "
            f"{role_counts['free']}/{role_counts['vip']}/{role_counts['academy']}\n"
            f"Membership records: {len(memberships)}\n\n"
            + ("\n".join(bound_ids) if bound_ids else "No groups bound yet.")
        )

    @bot.chat_member_handler()
    def chat_member_update(m):
        try:
            uid = str(m.new_chat_member.user.id)
            status = str(m.new_chat_member.status)
            chat = m.chat
            state_manager.atomic_update(
                lambda db: _record_membership(db, uid, chat, status)
            )
        except Exception as exc:
            print(
                "[COMMUNITY] chat_member update failed:",
                type(exc).__name__,
                str(exc)[:160],
            )

    @bot.my_chat_member_handler()
    def bot_membership_update(m):
        try:
            member = m.new_chat_member
            status = str(member.status)
            chat = m.chat

            def mutate(db):
                groups = db.setdefault("community_groups", {})
                chat_id = str(chat.id)
                group = groups.setdefault(chat_id, {})
                group.update(_chat_snapshot(chat))
                group["bot_status"] = status
                group["bot_status_updated_at"] = datetime.now(timezone.utc).isoformat()

            state_manager.atomic_update(mutate)
        except Exception as exc:
            print(
                "[COMMUNITY] bot membership update failed:",
                type(exc).__name__,
                str(exc)[:160],
            )
