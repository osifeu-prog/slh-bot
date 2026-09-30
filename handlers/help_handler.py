def register(bot):
    @bot.message_handler(commands=["faq"])
    def faq_cmd(msg):
        try:
            from core.faq_service import telegram_faq
            bot.reply_to(msg, telegram_faq())
        except Exception:
            bot.reply_to(msg, "FAQ לא זמין כרגע.")

    def _runtime_command_names(include_aliases=True):
        """Return commands actually registered on this bot instance."""
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
                found.add(command)
        if not include_aliases:
            found -= {"/allcommands", "/commands", "/comands"}
        return sorted(found)

    def _render_runtime_commands(commands):
        return (
            "📘 SLH OS — פקודות הרשומות בפועל\n\n"
            f"סה״כ פקודות/aliases: {len(commands)}\n\n"
            + " ".join(commands)
            + "\n\n🧭 מקור: Telegram handlers שנטענו ב-runtime."
        )

    @bot.message_handler(commands=["help", "allcommands", "commands", "comands"])
    def help_cmd(msg):
        commands = _runtime_command_names(include_aliases=True)
        try:
            from core.authority import is_owner
            owner = bool(is_owner(str(msg.from_user.id)))
        except Exception:
            owner = False

        requested = (
            msg.text.split()[0].split("@")[0].lower()
            if msg.text else "/help"
        )
        if requested in {"/allcommands", "/commands", "/comands"} and not owner:
            bot.reply_to(msg, "⛔ רשימת כל פקודות המערכת זמינה לבעלים בלבד.")
            return

        bot.reply_to(msg, _render_runtime_commands(commands))
