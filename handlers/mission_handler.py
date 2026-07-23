
import json, os, datetime

MISSION_FILE = "state/missions/board.json"

def register(bot):
    @bot.message_handler(commands=['mission'])
    def mission_cmd(m):
        parts = m.text.split(' ', 2)
        if len(parts) < 2:
            bot.reply_to(m, "שימוש: /mission add <תיאור> | list | assign <id> <agent> | done <id> | rewards")
            return
        action = parts[1].lower()
        board = load_board()
        missions = board.get("missions", [])

        if action == 'add':
            desc = parts[2] if len(parts) > 2 else "משימה ללא תיאור"
            missions.append({
                "id": len(missions) + 1,
                "desc": desc,
                "status": "open",
                "assigned_to": None,
                "reward": 0,
                "created": datetime.datetime.now().isoformat()
            })
            save_board(board)
            bot.reply_to(m, f"✅ משימה #{missions[-1]['id']} נוספה: {desc}")

        elif action == 'list':
            if not missions:
                bot.reply_to(m, "אין משימות.")
            else:
                msg = "📋 **לוח משימות SLH**\n\n"
                for t in missions:
                    icon = "🟢" if t['status'] == 'done' else "🔴" if t['status'] == 'open' else "🟡"
                    agent = t['assigned_to'] or "לא שויך"
                    msg += f"{icon} #{t['id']}: {t['desc']}\n   ↳ אחראי: {agent} | שכר: {t['reward']} SLH\n\n"
                bot.reply_to(m, msg, parse_mode='Markdown')

        elif action == 'assign':
            args = parts[2].split()
            if len(args) < 2:
                bot.reply_to(m, "שימוש: /mission assign <id> <שם סוכן>")
                return
            mid = int(args[0])
            agent = args[1]
            for t in missions:
                if t['id'] == mid:
                    t['assigned_to'] = agent
                    t['status'] = 'assigned'
                    save_board(board)
                    bot.reply_to(m, f"✅ משימה #{mid} שויכה ל‑{agent}")
                    return
            bot.reply_to(m, "❌ משימה לא נמצאה")

        elif action == 'done':
            try:
                mid = int(parts[2])
            except:
                bot.reply_to(m, "שימוש: /mission done <id>")
                return
            for t in missions:
                if t['id'] == mid:
                    t['status'] = 'done'
                    if t['assigned_to']:
                        award_reward(t['assigned_to'], t['reward'], t['id'])
                    save_board(board)
                    bot.reply_to(m, f"✅ משימה #{mid} הושלמה! התמול הועבר.")
                    return
            bot.reply_to(m, "❌ משימה לא נמצאה")

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

def load_board():
    if not os.path.exists(MISSION_FILE):
        return {"missions": [], "rules": {"new_agents_first_task": "system_contribution", "difficulty_levels": ["beginner","intermediate","advanced","expert"]}}
    with open(MISSION_FILE, 'r') as f:
        return json.load(f)

def save_board(board):
    os.makedirs(os.path.dirname(MISSION_FILE), exist_ok=True)
    with open(MISSION_FILE, 'w') as f:
        json.dump(board, f, indent=2, ensure_ascii=False)

def load_ledger():
    try:
        with open("state/rewards_ledger.json") as f:
            return json.load(f)
    except:
        return []
def award_reward(agent, amount, mission_id=None):
    ledger = load_ledger()
    ledger.append({
        "agent": agent,
        "amount": amount,
        "time": datetime.datetime.now().isoformat(),
        "mission_id": mission_id
    })
    with open("state/rewards_ledger.json", 'w') as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)
