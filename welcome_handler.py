from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json

ADMIN_IDS = ("8789977826",)

def init(bot):

    @bot.message_handler(commands=["start"])
    def send_welcome(message):
        uid = str(message.chat.id)
        name = ""
        try:
            with open("state/db.json") as f:
                db = json.load(f)
            name = db.get("users", {}).get(uid, {}).get("name", "")
        except:
            pass
        try:
            with open("logo.txt") as lf:
                logo = lf.read()
            bot.send_message(message.chat.id, f"```\n{logo}\n```", parse_mode="Markdown")
        except:
            pass
        greeting = f"\u05e0\u05e2\u05d9\u05dd \u05dc\u05e8\u05d0\u05d5\u05ea\u05da \u05e9\u05d5\u05d1, {name}!" if name else "\U0001f31f \u05d1\u05e8\u05d5\u05db\u05d9\u05dd \u05d4\u05d1\u05d0\u05d9\u05dd \u05dc-SLH OS!"
        txt = greeting + "\n\n<b>\u05de\u05e2\u05e8\u05db\u05ea \u05d4\u05e4\u05e2\u05dc\u05d4 \u05d7\u05db\u05de\u05d4</b> \u2013 \u05e7\u05d5\u05e8\u05e1\u05d9\u05dd, \u05e1\u05d5\u05db\u05e0\u05d9 AI, \u05d4\u05e9\u05e7\u05e2\u05d5\u05ea, \u05d5\u05db\u05dc\u05db\u05dc\u05d4 \u05d3\u05d9\u05d2\u05d9\u05d8\u05dc\u05d9\u05ea.\n\U0001f447 \u05d1\u05d7\u05e8 \u05d0\u05e4\u05e9\u05e8\u05d5\u05ea \u05dc\u05d4\u05ea\u05d7\u05d9\u05dc:"
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("\U0001f4da \u05e7\u05d5\u05e8\u05e1\u05d9\u05dd", callback_data="menu_courses"),
            InlineKeyboardButton("\U0001f4b0 \u05db\u05dc\u05db\u05dc\u05d4", callback_data="menu_economy"),
            InlineKeyboardButton("\U0001f916 \u05e1\u05d5\u05db\u05e0\u05d9\u05dd", callback_data="menu_agents"),
            InlineKeyboardButton("\U0001f4ca \u05d4\u05ea\u05e7\u05d3\u05de\u05d5\u05ea", callback_data="menu_progress"),
            InlineKeyboardButton("\U0001f6d2 \u05d7\u05e0\u05d5\u05ea", callback_data="menu_market"),
            InlineKeyboardButton("\u2753 \u05e2\u05d6\u05e8\u05d4", callback_data="menu_help"),
        )
        if uid in ADMIN_IDS:
            markup.add(InlineKeyboardButton("\U0001f527 \u05d0\u05d3\u05de\u05d9\u05df", callback_data="menu_admin"))
        bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")

    def main_markup(uid):
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("\U0001f4da \u05e7\u05d5\u05e8\u05e1\u05d9\u05dd", callback_data="menu_courses"),
            InlineKeyboardButton("\U0001f4b0 \u05db\u05dc\u05db\u05dc\u05d4", callback_data="menu_economy"),
            InlineKeyboardButton("\U0001f916 \u05e1\u05d5\u05db\u05e0\u05d9\u05dd", callback_data="menu_agents"),
            InlineKeyboardButton("\U0001f4ca \u05d4\u05ea\u05e7\u05d3\u05de\u05d5\u05ea", callback_data="menu_progress"),
            InlineKeyboardButton("\U0001f6d2 \u05d7\u05e0\u05d5\u05ea", callback_data="menu_market"),
            InlineKeyboardButton("\u2753 \u05e2\u05d6\u05e8\u05d4", callback_data="menu_help"),
        )
        if uid in ADMIN_IDS:
            markup.add(InlineKeyboardButton("\U0001f527 \u05d0\u05d3\u05de\u05d9\u05df", callback_data="menu_admin"))
        return markup

    @bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
    def handle_menu(call):
        uid = str(call.message.chat.id)
        action = call.data[5:]
        if action == "courses":
            m = InlineKeyboardMarkup(row_width=1)
            m.add(
                InlineKeyboardButton("\u25b6\ufe0f Bitcoin Mastery", callback_data="course_start_bitcoin_mastery"),
                InlineKeyboardButton("\U0001f4d6 \u05d4\u05e9\u05d9\u05e2\u05d5\u05e8 \u05d4\u05d1\u05d0", callback_data="course_next"),
                InlineKeyboardButton("\U0001f4ca \u05d4\u05ea\u05e7\u05d3\u05de\u05d5\u05ea", callback_data="menu_progress"),
                InlineKeyboardButton("\U0001f519 \u05d7\u05d6\u05e8\u05d4", callback_data="menu_back"),
            )
            bot.edit_message_text("\U0001f4da <b>\u05d4\u05e7\u05d5\u05e8\u05e1\u05d9\u05dd \u05e9\u05dc\u05d9</b>\n\n\u05e7\u05d5\u05e8\u05e1 \u05d6\u05de\u05d9\u05df: Bitcoin Mastery", call.message.chat.id, call.message.message_id, reply_markup=m, parse_mode="HTML")
        elif action == "economy":
            m = InlineKeyboardMarkup(row_width=2)
            m.add(
                InlineKeyboardButton("\U0001f4b0 \u05d9\u05ea\u05e8\u05d4", callback_data="econ_balance"),
                InlineKeyboardButton("\U0001f6d2 \u05e8\u05db\u05d9\u05e9\u05d4", callback_data="econ_buy"),
                InlineKeyboardButton("\u2b50 Stars", callback_data="econ_pay"),
                InlineKeyboardButton("\U0001f517 \u05d4\u05e4\u05e0\u05d9\u05d5\u05ea", callback_data="econ_referral"),
                InlineKeyboardButton("\U0001f519 \u05d7\u05d6\u05e8\u05d4", callback_data="menu_back"),
            )
            bot.edit_message_text("\U0001f4b0 <b>\u05de\u05e2\u05e8\u05db\u05ea \u05db\u05dc\u05db\u05dc\u05d4</b>", call.message.chat.id, call.message.message_id, reply_markup=m, parse_mode="HTML")
        elif action == "agents":
            m = InlineKeyboardMarkup(row_width=2)
            m.add(
                InlineKeyboardButton("\U0001f4cb \u05e1\u05d5\u05db\u05e0\u05d9\u05dd", callback_data="agent_list"),
                InlineKeyboardButton("\u2795 \u05e6\u05d5\u05e8 \u05e1\u05d5\u05db\u05df", callback_data="agent_create"),
                InlineKeyboardButton("\U0001f4ec \u05d3\u05d5\u05d0\u05e8", callback_data="agent_inbox"),
                InlineKeyboardButton("\U0001f519 \u05d7\u05d6\u05e8\u05d4", callback_data="menu_back"),
            )
            bot.edit_message_text("\U0001f916 <b>\u05e1\u05d5\u05db\u05e0\u05d9 AI</b>", call.message.chat.id, call.message.message_id, reply_markup=m, parse_mode="HTML")
        elif action == "progress":
            try:
                with open("state/db.json") as f:
                    db = json.load(f)
                user = db.get("users", {}).get(uid, {})
                name = user.get("name", "?")
                course = user.get("courses", {}).get("bitcoin_mastery", {})
                prog = course.get("progress", 0)
                stage = course.get("current_stage", 1)
                tasks = db.get("user_tasks", {}).get(uid, [])
                bal = user.get("balance", 0)
                pts = user.get("points", 0)
                refs = user.get("referral_count", 0)
                txt = f"\U0001f4ca <b>\u05d4\u05ea\u05e7\u05d3\u05de\u05d5\u05ea \u05e9\u05dc {name}</b>\n\n\U0001f4da \u05e7\u05d5\u05e8\u05e1: {prog}% (\u05e9\u05dc\u05d1 {stage})\n\u2705 \u05de\u05e9\u05d9\u05de\u05d5\u05ea: {len(tasks)}\n\U0001f517 \u05d4\u05e4\u05e0\u05d9\u05d5\u05ea: {refs}\n\u2b50 \u05e0\u05e7\u05d5\u05d3\u05d5\u05ea: {pts}\n\U0001f4b0 \u05e7\u05e8\u05d3\u05d9\u05d8\u05d9\u05dd: {bal}"
            except:
                txt = "\U0001f4ca \u05dc\u05d0 \u05e0\u05de\u05e6\u05d0 \u05de\u05d9\u05d3\u05e2. /join"
            m = InlineKeyboardMarkup(row_width=1)
            m.add(
                InlineKeyboardButton("\U0001f4cb \u05de\u05e9\u05d9\u05de\u05d5\u05ea", callback_data="task_list"),
                InlineKeyboardButton("\U0001f519 \u05d7\u05d6\u05e8\u05d4", callback_data="menu_back"),
            )
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=m, parse_mode="HTML")
        elif action == "market":
            m = InlineKeyboardMarkup(row_width=1)
            m.add(
                InlineKeyboardButton("\U0001f6cd \u05e2\u05d9\u05d9\u05df \u05d1\u05d7\u05e0\u05d5\u05ea", callback_data="market_browse"),
                InlineKeyboardButton("\U0001f4e6 \u05de\u05d4 \u05d4\u05ea\u05e7\u05e0\u05ea\u05d9", callback_data="market_installed"),
                InlineKeyboardButton("\U0001f519 \u05d7\u05d6\u05e8\u05d4", callback_data="menu_back"),
            )
            bot.edit_message_text("\U0001f6d2 <b>Marketplace</b>", call.message.chat.id, call.message.message_id, reply_markup=m, parse_mode="HTML")
        elif action == "help":
            m = InlineKeyboardMarkup(row_width=1)
            m.add(
                InlineKeyboardButton("\U0001f4d8 \u05db\u05dc \u05d4\u05e4\u05e7\u05d5\u05d3\u05d5\u05ea", callback_data="help_commands"),
                InlineKeyboardButton("\U0001f393 \u05de\u05d3\u05e8\u05d9\u05da \u05dc\u05de\u05ea\u05d7\u05d9\u05dc\u05d9\u05dd", callback_data="help_guide"),
                InlineKeyboardButton("\U0001f519 \u05d7\u05d6\u05e8\u05d4", callback_data="menu_back"),
            )
            bot.edit_message_text("\u2753 <b>\u05e2\u05d6\u05e8\u05d4</b>", call.message.chat.id, call.message.message_id, reply_markup=m, parse_mode="HTML")
        elif action == "admin":
            if uid not in ADMIN_IDS:
                bot.answer_callback_query(call.id, "\u26d4\ufe0f \u05d0\u05d9\u05df \u05d4\u05e8\u05e9\u05d0\u05d4")
                return
            m = InlineKeyboardMarkup(row_width=2)
            m.add(
                InlineKeyboardButton("\U0001f4ca \u05e1\u05d8\u05d8\u05d5\u05e1", callback_data="admin_status"),
                InlineKeyboardButton("\U0001f465 \u05de\u05e9\u05ea\u05de\u05e9\u05d9\u05dd", callback_data="admin_users"),
                InlineKeyboardButton("\U0001f4e2 \u05e9\u05d9\u05d3\u05d5\u05e8", callback_data="admin_broadcast"),
                InlineKeyboardButton("\U0001f4b0 \u05d4\u05db\u05e0\u05e1\u05d5\u05ea", callback_data="admin_revenue"),
                InlineKeyboardButton("\U0001f519 \u05d7\u05d6\u05e8\u05d4", callback_data="menu_back"),
            )
            bot.edit_message_text("\U0001f527 <b>\u05dc\u05d5\u05d7 \u05de\u05e0\u05d4\u05dc</b>", call.message.chat.id, call.message.message_id, reply_markup=m, parse_mode="HTML")
        elif action == "back":
            bot.edit_message_text("<b>\u05de\u05e2\u05e8\u05db\u05ea \u05d4\u05e4\u05e2\u05dc\u05d4 \u05d7\u05db\u05de\u05d4</b> \u2013 \u05d1\u05d7\u05e8 \u05d0\u05e4\u05e9\u05e8\u05d5\u05ea:", call.message.chat.id, call.message.message_id, reply_markup=main_markup(uid), parse_mode="HTML")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("course_"))
    def handle_course(call):
        bot.answer_callback_query(call.id)
        if call.data.startswith("course_start_"):
            cid = call.data.replace("course_start_", "")
            bot.send_message(call.message.chat.id, f"\u25b6\ufe0f \u05e9\u05dc\u05d7 /start_course {cid}")
        elif call.data == "course_next":
            bot.send_message(call.message.chat.id, "\U0001f4d6 \u05e9\u05dc\u05d7 /next")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("econ_"))
    def handle_econ(call):
        bot.answer_callback_query(call.id)
        a = call.data[5:]
        cmds = {"balance": "/balance", "buy": "/buy", "pay": "/pay", "referral": "/referral"}
        if a in cmds:
            bot.send_message(call.message.chat.id, cmds[a])

    @bot.callback_query_handler(func=lambda call: call.data.startswith("agent_"))
    def handle_agent(call):
        bot.answer_callback_query(call.id)
        a = call.data[6:]
        if a == "list": bot.send_message(call.message.chat.id, "/agents")
        elif a == "create": bot.send_message(call.message.chat.id, "/agent_create <\u05e9\u05dd>")
        elif a == "inbox": bot.send_message(call.message.chat.id, "/inbox <\u05e9\u05dd>")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("market_"))
    def handle_market(call):
        bot.answer_callback_query(call.id)
        if call.data == "market_browse": bot.send_message(call.message.chat.id, "/market")
        elif call.data == "market_installed": bot.send_message(call.message.chat.id, "/market_installed")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("task_"))
    def handle_task(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "/task list")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("help_"))
    def handle_help(call):
        bot.answer_callback_query(call.id)
        if call.data == "help_commands": bot.send_message(call.message.chat.id, "/help")
        elif call.data == "help_guide":
            bot.send_message(call.message.chat.id, "\U0001f393 <b>\u05de\u05d3\u05e8\u05d9\u05da \u05de\u05d4\u05d9\u05e8:</b>\n\n1\ufe0f\u20e3 /join\n2\ufe0f\u20e3 /start_course bitcoin_mastery\n3\ufe0f\u20e3 /next\n4\ufe0f\u20e3 /task create <\u05d8\u05e7\u05e1\u05d8>\n5\ufe0f\u20e3 /balance\n6\ufe0f\u20e3 /agents", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
    def handle_admin_cb(call):
        if str(call.message.chat.id) not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "\u26d4\ufe0f"); return
        bot.answer_callback_query(call.id)
        cmds = {"status": "/status", "users": "/users", "broadcast": "/broadcast", "revenue": "/revenue"}
        a = call.data[6:]
        if a in cmds: bot.send_message(call.message.chat.id, cmds[a])

    @bot.message_handler(commands=["join"])
    def start_join(m):
        uid = str(m.chat.id)
        try:
            with open("state/db.json") as f:
                db = json.load(f)
            if uid in db.get("users", {}):
                bot.reply_to(m, "\u05d0\u05ea\u05d4 \u05db\u05d1\u05e8 \u05e8\u05e9\u05d5\u05dd!\n/myprogress"); return
        except: pass
        msg = bot.reply_to(m, "\u05d1\u05e8\u05d5\u05db\u05d9\u05dd \u05d4\u05d1\u05d0\u05d9\u05dd! \u05de\u05d4 \u05e9\u05de\u05da \u05d4\u05de\u05dc\u05d0?")
        bot.register_next_step_handler(msg, process_join_name)

    def process_join_name(m):
        name = m.text.strip()
        if not name:
            msg = bot.reply_to(m, "\u05d4\u05e9\u05dd \u05dc\u05d0 \u05d9\u05db\u05d5\u05dc \u05dc\u05d4\u05d9\u05d5\u05ea \u05e8\u05d9\u05e7. \u05de\u05d4 \u05e9\u05de\u05da?")
            bot.register_next_step_handler(msg, process_join_name); return
        bot._join_name = {str(m.chat.id): name}
        msg = bot.reply_to(m, f"\u05e9\u05dc\u05d5\u05dd {name}! \u05de\u05d4 \u05d4\u05de\u05d8\u05e8\u05d4 \u05e9\u05dc\u05da?")
        bot.register_next_step_handler(msg, process_join_goal)

    def process_join_goal(m):
        uid = str(m.chat.id)
        goal = m.text.strip()
        name = getattr(bot, "_join_name", {}).get(uid, "\u05de\u05e9\u05ea\u05de\u05e9")
        try:
            with open("state/db.json") as f: db = json.load(f)
        except: db = {"users": {}}
        db.setdefault("users", {})[uid] = {"name": name, "goal": goal, "balance": 0, "points": 0, "referral_count": 0, "courses": {}}
        with open("state/db.json", "w") as f: json.dump(db, f, indent=2, ensure_ascii=False)
        bot.reply_to(m, f"\u2705 \u05e0\u05e8\u05e9\u05de\u05ea \u05d1\u05d4\u05e6\u05dc\u05d7\u05d4!\n\u05e9\u05dd: {name}\n\u05de\u05d8\u05e8\u05d4: {goal}\n\n/start")
