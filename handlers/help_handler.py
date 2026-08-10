def register(bot):
    @bot.message_handler(commands=['help'])
    def help_cmd(msg):
        text = """📘 SLH Commands

👤 Account
/start – Welcome
/join – Register
/me – Your profile
/profile – Detailed profile

📚 Learning
/courses – List courses
/course_slh – SLH course
/lesson – Start lesson
/finish – Finish lesson
/progress – Your progress
/map – Learning map

🤖 Agents
/agents – List agents
/agent_create <name> – Create agent
/agent_delete <id> – Delete agent
/agentstate <prefix> <state> – Set state
/sendagent <prefix> <msg> – Send message
/inbox <prefix> – Check inbox

💰 Economy
/balance – Check balance
/pay – Make payment
/buy – Purchase items
/revenue – Revenue status

📋 Tasks & Missions
/task – Manage tasks
/task_add – Add task
/mission – Mission control
/complete – Mark complete

🗳 Voting
/vote <id> <yes/no> – Vote
/propose <text> – Create proposal
/tally <id> – Show results

📡 Devices
/device_register <name>
/device_list
/device_status <id>
/device_delete <id>
/device_heartbeat

🏆 Leaderboard
/top – Top learners

🛠 Admin
/admin – Admin panel
/exec <cmd> – Shell (admin)
/backup – Backup DB
/megadiag – Full diagnostic
/health – Health check
/status – System status
/deploy – Trigger deploy

💬 Ask & Help
/ask <question> – Ask AI
/help – This menu
"""
        bot.reply_to(msg, text)


