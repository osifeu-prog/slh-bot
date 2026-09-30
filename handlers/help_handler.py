def register(bot):
    MAX_TELEGRAM_MESSAGE = 3500
    OWNER_ONLY_COMMANDS = {
        "/admin", "/admin_status", "/allcommands", "/commands", "/comands",
        "/e", "/exec", "/execr", "/autoexec", "/deploy", "/redeploy", "/logs",
        "/vault", "/vault_verify", "/vault_add", "/vault_rotate", "/vault_remove",
        "/vault_health", "/vault_exposed", "/vault_log", "/vault_help",
        "/biz", "/biz_users", "/biz_revenue", "/biz_ai", "/biz_bots",
        "/bot_seed", "/bot_register", "/bot_status", "/bots", "/botcontrol",
        "/dev_add", "/dev_remove", "/dev_lock", "/dev_revoke", "/dev_activate",
        "/dev_reward", "/dev_list", "/dev_perm", "/dev_role",
        "/dev_request", "/dev_requests", "/dev_approve", "/dev_deny",
        "/developer_lab", "/developer_access",
        "/backup", "/clean", "/recovery", "/recovery_verify",
        "/ownership_transfer", "/reconcile", "/recon_release",
        "/revenue_audit", "/revenue_reconcile",
    }

    def _runtime_command_names(include_sensitive):
        found = set()
        for handler in getattr(bot, "message_handlers", []) or []:
            filters = handler.get("filters") or {}
            commands = filters.get("commands") or []
            if isinstance(commands, str):
                commands = [commands]
            for command in commands:
                command = str(command or "").strip().lower()
                if not command:
                    continue
                if not command.startswith("/"):
                    command = "/" + command
                if not include_sensitive and command in OWNER_ONLY_COMMANDS:
                    continue
                found.add(command)
        return sorted(found)

    def _send_chunked(msg, title, commands):
        lines = [title, "", f"סה״כ: {len(commands)}", ""]
        current = "\n".join(lines)
        for command in commands:
            addition = command + " "
            if len(current) + len(addition) > MAX_TELEGRAM_MESSAGE and current.strip():
                bot.reply_to(msg, current.rstrip())
                current = ""
            current += addition
        if current.strip():
            bot.reply_to(msg, current.rstrip())

    @bot.message_handler(commands=["faq"])
    def faq_cmd(msg):
        try:
            from core.faq_service import telegram_faq
            bot.reply_to(msg, telegram_faq())
        except Exception:
            bot.reply_to(msg, "FAQ לא זמין כרגע.")

    @bot.message_handler(commands=["help", "allcommands", "commands", "comands"])
    def help_cmd(msg):
        requested = (
            msg.text.split()[0].split("@")[0].lower()
            if msg.text else "/help"
        )
        try:
            from core.authority import is_owner
            owner = bool(is_owner(str(msg.from_user.id)))
        except Exception:
            owner = False

        complete = requested in {"/allcommands", "/commands", "/comands"}
        if complete and not owner:
            bot.reply_to(msg, "⛔ רשימת כל פקודות המערכת זמינה לבעלים בלבד.")
            return

        commands = _runtime_command_names(include_sensitive=complete and owner)
        if complete:
            _send_chunked(
                msg,
                "📘 SLH OS — כל הפקודות הרשומות בפועל",
                commands,
            )
        else:
            _send_chunked(
                msg,
                "📘 SLH OS — פקודות משתמש זמינות",
                commands,
            )

