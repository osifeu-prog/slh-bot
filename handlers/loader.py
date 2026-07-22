def load_handlers(bot, context):

    @bot.message_handler(commands=['register'])
    def register_redirect(m):
        bot.reply_to(m, '👋 נא להשתמש ב־/join להרשמה:')
        from handlers.join_handler import register as jr
        jr(bot)
        # call join_start manually
        for h in bot.message_handlers:
            if hasattr(h, 'name') and h.name == 'join_start':
                h(m)
                break

    print("🔄 Loading modular handlers...")

    # ===== MODULAR HANDLERS =====
    try:
        from handlers.agents_handler import register as register_agents
        register_agents(bot, context)
    except Exception as e:
        print("agents_handler error:", e)

    try:
        from handlers.task_handler import register as register_task
        register_task(bot, context)
    except Exception as e:
        print("task_handler error:", e)

    try:
        from handlers.morning_handler import register as register_morning
        register_morning(bot, context)
    except Exception as e:
        print("morning_handler error:", e)

    try:
        from handlers.system_handler import register as register_system
        from state.custom_handlers.ai_voting_handler import register as register_ai_voting
        register_system(bot, context)
    except Exception as e:
        print("system_handler error:", e)



    # ===== CHAT REGISTRY =====
    try:
        from handlers.chat_registry_handler import register as register_chat_registry
        register_chat_registry(bot)
        print("💬 Chat registry handler loaded")
    except Exception as e:
        print("chat_registry error:", e)


    # ===== SLH GATEWAY BRIDGE =====
    try:
        from handlers.gateway_handler import register as register_gateway
        register_gateway(bot)
        print("🌐 SLH Gateway handler loaded")
    except Exception as e:
        print("gateway_handler error:", e)



    # ===== CONTROL TOWER =====
    try:
        @bot.message_handler(commands=['control'])
        def control_cmd(m):
            import json, os, time
            db = json.load(open('state/db.json'))
            users = len(db.get('users', {}))
            agents_all = db.get('agents', {})
            agents_active = sum(1 for a in agents_all.values() if a.get('state') == 'active')
            agents_idle = sum(1 for a in agents_all.values() if a.get('state') == 'idle')
            agents_busy = sum(1 for a in agents_all.values() if a.get('state') == 'busy')
            token = db.get('token', {})
            token_supply = token.get('supply', 'N/A')
            votes = len(db.get('votes', {}))
            # commands loaded – estimate from handler files
            import subprocess
            cmds = subprocess.getoutput("grep -r '@bot.message_handler' handlers/ | wc -l").strip()
            # last commit
            commit = os.popen("git log -1 --format='%h %s'").read().strip() or "N/A"
            bot.reply_to(m,
                f"🧠 SLH OS CONTROL TOWER\n\n"
                f"🟢 System: Online\n"
                f"📦 DB: state/db.json\n\n"
                f"👥 Users: {users}\n"
                f"🤖 Agents: {len(agents_all)} (🟢{agents_active} 🟡{agents_idle} 🔴{agents_busy})\n"
                f"💰 Token Supply: {token_supply}\n"
                f"🗳 Votes: {votes}\n"
                f"📡 Commands loaded: ~{cmds}\n"
                f"🔧 Last Deploy: {commit}\n"
                f"\n/control agents | /control economy | /control health"
            )
    except Exception as e:
        print("control_handler error:", e)

    # ===== AGENT ONBOARDING =====
    try:
        @bot.message_handler(commands=['agent_onboard'])
        def agent_onboard(m):
            import json, time
            parts = m.text.split(maxsplit=2)
            if len(parts) < 2:
                bot.reply_to(m, "Usage: /agent_onboard <name> [description]")
                return
            name = parts[1]
            desc = parts[2] if len(parts) > 2 else "New AI agent"
            uid = str(m.from_user.id)
            db = json.load(open('state/db.json'))
            agents = db.get('agents', {})
            
            # בדיקת כפילות
            if name in [a.get('name') for a in agents.values()]:
                bot.reply_to(m, f"❌ Agent '{name}' already exists")
                return
            
            # יצירת סוכן חדש עם schema אחיד
            nid = str(max([int(k) for k in agents.keys() if k.isdigit()] + [0]) + 1)
            agents[nid] = {
                "name": name,
                "role": "ai_assistant",
                "state": "idle",
                "inbox": [],
                "outbox": [],
                "history": [],
                "created": time.time(),
                "description": desc,
                "permissions": ["read", "vote", "propose"],
                "onboarded_by": uid
            }
            db['agents'] = agents
            json.dump(db, open('state/db.json','w'), indent=2, ensure_ascii=False)
            
            # שליחת הודעת ברוכים הבאים לסוכן
            bot.reply_to(m, f"🎉 Agent '{name}' onboarded successfully!\n"
                           f"🆔 ID: {nid}\n"
                           f"📝 {desc}\n\n"
                           f"Welcome to SLH OS! You can now:\n"
                           f"• Read proposals\n"
                           f"• Vote on decisions\n"
                           f"• Propose new ideas\n"
                           f"• Receive tasks via inbox\n\n"
                           f"Your AI assistant will help you get started.")
        print("✅ agent_onboard handler loaded")
    except Exception as e:
        print("agent_onboard error:", e)
    # ===== LEGACY USER EXPERIENCE =====
    legacy = [
        "welcome_handler",
        "onboarding_handler",
        "help_handler",
        "course_handlers",
        "learn_handlers",
        "econ_handler",
        "payment_handler",
        "project_commands",
        "smart_leaderboard",
        "report_handler",
    ]

    for module_name in legacy:
        try:
            module = __import__(module_name)

            # handlers with register(bot)
            if hasattr(module, "register"):
                module.register(bot)

            # report uses init(bot)
            elif module_name == "report_handler" and hasattr(module, "init"):
                module.init(bot)

            # welcome uses init(bot)
            elif module_name == "welcome_handler" and hasattr(module, "init"):
                module.init(bot)

            # onboarding uses init(bot)
            elif module_name == "onboarding_handler" and hasattr(module, "init"):
                print(">>> LOADING ONBOARDING HANDLER")
                module.init(bot)
                print(">>> ONBOARDING HANDLER LOADED")

            # help uses register_help(bot)
            elif module_name == "help_handler" and hasattr(module, "register_help"):
                module.register_help(bot)

            # course/economy style handlers
            elif module_name == "course_handlers" and hasattr(module, "register_course_handlers"):
                module.register_course_handlers(bot)

            elif module_name == "econ_handler" and hasattr(module, "register_econ_handlers"):
                module.register_econ_handlers(bot)

            elif module_name == "payment_handler" and hasattr(module, "register_payment_handlers"):
                module.register_payment_handlers(bot)

            elif module_name == "smart_leaderboard" and hasattr(module, "register"):
                module.register(bot)

        except Exception as e:
            print(f"{module_name} load error:", e)


    # ===== ECONOMY DASHBOARD =====
    try:
        import json
        @bot.message_handler(commands=["economy"])
        def economy_cmd(m):
            uid = str(m.from_user.id)
            db = json.load(open("state/db.json"))
            user = db.get("users", {}).get(uid, {})
            credits = user.get("wallet", {}).get("credits", 0)
            points = user.get("gamification", {}).get("points", 0)
            token = db.get("token", {}).get("balances", {}).get(uid, 0)
            bot.reply_to(m, f"💰 Economy Dashboard\n🔹 Credits: {credits}\n🔹 Points: {points}\n🔹 SLH: {token}")
    except Exception as e:
        print("economy_handler error:", e)
    print("🧩 Modular + Legacy handlers loaded")
    from handlers.kb_handler import register as reg_kb; reg_kb(bot)
    register_ai_voting(bot, None)
    try:
        from handlers.join_handler import register as register_join
        register_join(bot)
        print("👤 join_handler loaded")
    except Exception as e:
        print("join_handler error:", e)
    try:
        from handlers.mission_handler import register as register_mission
        register_mission(bot)
        print("📋 mission_handler loaded")
    except Exception as e:
        print("mission_handler error:", e)
    try:
        from advanced_ask_handler import register_ask_handler
        register_ask_handler(bot, context)
        print("🔥 ASK HANDLER REGISTERED ON BOT:", id(bot))
        print("✅ advanced_ask_handler loaded")
    except Exception as e:
        print("advanced_ask_handler error:", e)
