import state_manager

from core.mission_state import MissionStateNormalizer
from core.mission_runtime_bridge import execute_mission_via_runtime
from core.mission_lifecycle import MissionLifecycleService
from core.mission_reward_service import issue_mission_reward


def register(bot, context=None):
    lifecycle = context.get("mission_lifecycle") if isinstance(context, dict) else None
    if lifecycle is None:
        lifecycle = MissionLifecycleService(".")

    is_admin = context.get("is_admin") if isinstance(context, dict) else None

    def reward_after_completion(mission_id):
        board, _manifest = lifecycle.load_state()
        mission = lifecycle.find_mission(board, mission_id)
        if mission is None:
            return {"status": "blocked", "reason": "MISSION_NOT_FOUND"}
        if mission.get("status") != "completed":
            return {"status": "blocked", "reason": "MISSION_NOT_COMPLETED"}
        return issue_mission_reward(mission, mission_id=mission_id)

    @bot.message_handler(commands=["mission"])
    def mission_cmd(m):
        parts = m.text.split(" ", 2)
        if len(parts) < 2:
            bot.reply_to(m, "שימוש: /mission add <תיאור> | list | assign <id> <agent> | done <id> | run <id> | rewards")
            return

        action = parts[1].lower()
        if action in {"add", "assign", "done", "run"}:
            if not callable(is_admin) or not is_admin(m):
                bot.reply_to(m, "❌ פעולה זו זמינה ל-Owner בלבד.")
                return

        board, manifest = lifecycle.load_state()
        missions = board.get("missions", [])

        if action == "add":
            desc = parts[2] if len(parts) > 2 else "משימה ללא תיאור"
            numeric_ids = [int(t.get("id")) for t in missions if str(t.get("id")).isdigit()]
            next_id = str(max(numeric_ids or [0]) + 1)
            result = lifecycle.create_mission(next_id, desc, reward=0)
            if result.get("status") != "created":
                bot.reply_to(m, "❌ יצירת המשימה נחסמה: " + str(result.get("reason")))
                return
            bot.reply_to(m, f"✅ משימה #{next_id} נוספה: {desc}")
            return

        if action == "list":
            if not missions:
                bot.reply_to(m, "אין משימות.")
                return
            msg = "📋 **לוח משימות SLH**\n\n"
            for t in missions:
                status = t.get("status")
                icon = "🟢" if MissionStateNormalizer.is_completed(status) else "🔴" if status == "open" else "🟡"
                agent = t.get("assigned_to") or "לא שויך"
                msg += f"{icon} #{t.get('id')}: {t.get('desc', '')}\n   ↳ אחראי: {agent} | שכר: {t.get('reward', 0)} SLH\n\n"
            bot.reply_to(m, msg)
            return

        if action == "assign":
            if len(parts) < 3:
                bot.reply_to(m, "שימוש: /mission assign <id> <שם סוכן>")
                return
            args = parts[2].split()
            if len(args) < 2:
                bot.reply_to(m, "שימוש: /mission assign <id> <שם סוכן>")
                return
            result = lifecycle.assign_mission(args[0], args[1])
            if result.get("status") != "assigned":
                bot.reply_to(m, "❌ שיוך המשימה נחסם.\n" + str(result.get("checks") or result.get("reason", "unknown")))
                return
            bot.reply_to(m, f"✅ משימה #{args[0]} שויכה ל-{args[1]}")
            return

        if action == "done":
            if len(parts) < 3:
                bot.reply_to(m, "שימוש: /mission done <id>")
                return
            mission_id = parts[2].strip()
            completion = lifecycle.complete_mission(mission_id)
            if completion.get("status") not in {"completed"}:
                if completion.get("reason") != "mission_already_completed":
                    bot.reply_to(m, "❌ השלמת המשימה נחסמה.\n" + str(completion.get("checks") or completion.get("reason", "unknown")))
                    return
            reward = reward_after_completion(mission_id)
            if reward.get("status") in {"blocked", "pending"}:
                bot.reply_to(m, f"⚠️ המשימה הושלמה, אך התגמול ממתין: {reward.get('reason')}")
                return
            bot.reply_to(m, f"✅ משימה #{mission_id} הושלמה!\n💰 תגמול: {reward.get('reward', 0)} SLH")
            return

        if action == "run":
            if len(parts) < 3:
                bot.reply_to(m, "שימוש: /mission run <id>")
                return
            mission_id = parts[2].strip()
            try:
                result = execute_mission_via_runtime(mission_id=mission_id)
                reward = reward_after_completion(mission_id)
                result["reward"] = reward
                bot.reply_to(m, "🔵 תוצאת הרצת משימה #" + mission_id + "\n" + str(result))
            except Exception as e:
                bot.reply_to(m, "❌ שגיאה בהרצת משימה #" + mission_id + "\n" + str(e))
            return

        if action == "rewards":
            ledger = load_ledger()
            if not ledger:
                bot.reply_to(m, "אין תגמולים עדיין.")
                return
            lines = ["💰 **תגמולים**", ""]
            for entry in ledger[-10:]:
                meta = entry.get("meta") or {}
                mission_id = entry.get("mission_id", meta.get("mission_id"))
                if not mission_id:
                    continue
                uid = entry.get("uid", "?")
                amount = entry.get("amount", entry.get("credits", entry.get("delta", 0)))
                lines.append(f"👤 {uid}: {amount} SLH (משימה #{mission_id})")
            if len(lines) == 2:
                bot.reply_to(m, "אין תגמולי משימות עדיין.")
                return
            bot.reply_to(m, "\n".join(lines))
            return

        bot.reply_to(m, "פעולה לא מוכרת.")


def load_ledger():
    try:
        db = state_manager.load_db()
        ledger = db.get("ledger", [])
        return ledger if isinstance(ledger, list) else []
    except Exception:
        return []
