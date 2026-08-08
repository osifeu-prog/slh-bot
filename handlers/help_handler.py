def register_help(bot):
    @bot.message_handler(commands=["help"])
    def help_cmd(msg):
        text = """📘 SLH Commands

Getting Started
/start - Welcome
/join - Register
/me - Your profile
/help - This menu

Courses
/courses - List courses
/progress - Your progress

Agents
/agents - List agents
/agent_create - Create agent

Economy
/balance - Check balance
/pay - Make payment

System
/ask - Ask AI
/admin - Admin panel
/exec - Run command (admins)
"""
        bot.reply_to(msg, text)
