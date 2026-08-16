from core.firewall import firewall_status


def register(bot):
    @bot.message_handler(commands=["firewall"])
    def firewall_cmd(m):
        st = firewall_status(m.from_user.id)
        bot.reply_to(
            m,
            "🛡 SLH FIREWALL\n\n"
            f"👤 Role: {st['role']}\n"
            f"👑 Owner: {'✅' if st['is_owner'] else '❌'}\n"
            f"🔐 Permissions: {', '.join(st['permissions']) or 'none'}\n\n"
            "Protected commands:\n"
            "exec / deploy / restart / broadcast / db_write / git_push"
        )
