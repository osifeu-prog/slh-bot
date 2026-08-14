
import datetime


from core.mission_state import (
    MissionState,
    MissionStateNormalizer
)

from core.mission_runtime_bridge import execute_mission_via_runtime
from core.mission_lifecycle import (
    MissionLifecycleService
)

def register(bot, context=None):

    lifecycle = (
        context.get("mission_lifecycle")
        if isinstance(context, dict)
        else None
    )

    if lifecycle is None:
        lifecycle = MissionLifecycleService(".")

    @bot.message_handler(commands=['mission'])
    def mission_cmd(m):
        parts = m.text.split(' ', 2)
        if len(parts) < 2:
            bot.reply_to(m, "שימוש: /mission add <תיאור> | list | assign <id> <agent> | done <id> | rewards")
            return
        action = parts[1].lower()

        board, manifest = (
            lifecycle.load_state()
        )

        missions = board.get(
            "missions",
            []
        )

        if action == 'add':
            desc = (
                parts[2]
                if len(parts) > 2
                else "משימה ללא תיאור"
            )

            next_id = str(
                max(
                    [
                        int(
                            t.get("id")
                        )
                        for t in missions
                        if str(
                            t.get("id")
                        ).isdigit()
                    ]
                    or [0]
                )
                + 1
            )

            result = lifecycle.create_mission(
                mission_id=next_id,
                description=desc,
                reward=0
            )

            if result.get("status") != "created":
                bot.reply_to(
                    m,
                    "❌ יצירת המשימה נחסמה: "
                    + str(
                        result.get("reason")
                    )
                )
                return

            bot.reply_to(
                m,
                f"✅ משימה #{next_id} נוספה: {desc}"
            )

        elif action == 'list':
            if not missions:
                bot.reply_to(m, "אין משימות.")
            else:
                msg = "📋 **לוח משימות SLH**\n\n"
                for t in missions:
                    icon = "🟢" if MissionStateNormalizer.is_completed(t.get('status')) else "🔴" if t['status'] == 'open' else "🟡"
                    agent = t['assigned_to'] or "לא שויך"
                    msg += f"{icon} #{t['id']}: {t['desc']}\n   ↳ אחראי: {agent} | שכר: {t['reward']} SLH\n\n"
                bot.reply_to(m, msg, parse_mode='Markdown')

        elif action == 'assign':

            if len(parts) < 3:

                bot.reply_to(
                    m,
                    "שימוש: /mission assign <id> <שם סוכן>"
                )

                return

            args = parts[2].split()

            if len(args) < 2:

                bot.reply_to(
                    m,
                    "שימוש: /mission assign <id> <שם סוכן>"
                )

                return

            mission_id = args[0]

            agent_id = args[1]

            result = lifecycle.assign_mission(
                mission_id=mission_id,
                agent_id=agent_id
            )

            if result.get(
                "status"
            ) != "assigned":

                checks = result.get(
                    "checks",
                    {}
                )

                bot.reply_to(
                    m,
                    "❌ שיוך המשימה נחסם.\n"
                    + str(
                        checks
                        or result.get(
                            "reason",
                            "unknown"
                        )
                    )
                )

                return

            bot.reply_to(
                m,
                f"✅ משימה #{mission_id} שויכה ל-{agent_id}"
            )

        elif action == 'done':

            if len(parts) < 3:

                bot.reply_to(
                    m,
                    "שימוש: /mission done <id>"
                )

                return

            mission_id = parts[2].strip()

            result = lifecycle.complete_mission(
                mission_id=mission_id
            )

            if result.get(
                "status"
            ) != "completed":

                checks = result.get(
                    "checks",
                    {}
                )

                bot.reply_to(
                    m,
                    "❌ השלמת המשימה נחסמה.\n"
                    + str(
                        checks
                        or result.get(
                            "reason",
                            "unknown"
                        )
                    )
                )

                return

            bot.reply_to(
                m,
                f"✅ משימה #{mission_id} הושלמה!"
            )

        elif action == 'run':

            if len(parts) < 3:
                bot.reply_to(m, "שימוש: /mission run <id>")
                return

            mission_id = parts[2].strip()

            try:
                result = execute_mission_via_runtime(
                    mission_id=mission_id
                )

                bot.reply_to(
                    m,
                    "🔵 תוצאת הרצת משימה #"
                    + mission_id
                    + "\\n"
                    + str(result)
                )

            except Exception as e:

                bot.reply_to(
                    m,
                    "❌ שגיאה בהרצת משימה #"
                    + mission_id
                    + "\\n"
                    + str(e)
                )

        elif action == 'rewards':
            ledger = load_ledger()
            if not ledger:
                bot.reply_to(m, "אין תמולים עדיין.")
            else:
                msg = "💰 **תמולים**\n\n"
                for entry in ledger[-10:]:
                    msg += f"👤 {entry['agent']}: {entry['amount']} SLH (משימה #{entry['mission_id']})\n"
                bot.reply_to(m, msg, parse_mode='Markdown')

        else:
            bot.reply_to(m, "פעולה לא מוכרת.")

def load_ledger():
    try:
        with open("state/rewards_ledger.json") as f:
            return json.load(f)
    except:
        return []
