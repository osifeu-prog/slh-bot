def register_help(bot):
    @bot.message_handler(commands=['help'])
    def help_command(m):
        bot.send_message(m.chat.id, """📘 HELP & COMMANDS (user)
👋 Getting Started
/start – Welcome & menu
/join – Register for learning
/register – Alternative registration
/referral – Get referral link
/usereferral – Use referral code

📚 Courses
/courses – List all courses
/course <id> – Course details
/start_course <id> – Begin a course
/next – Next lesson
/endday – End current study session

📈 Progress & Reports
/progress – Your progress
/myprogress – Detailed stats
/myreport – Your report
/report – System report
/morning_report – Morning summary
/evening_report – Evening summary

🛠 Projects & Tasks
/project – Manage personal project
/task – Manage tasks
/complete – Mark task complete

📓 Journal
/journal – Write journal entry
/journal_read – Read your journal

🤖 Agents (user)
/agent_create <name> – Create an agent
/agents – Your agents
/agentstate <prefix> <state> – Set state
/sendagent <prefix> <msg> – Send message
/inbox <prefix> – Check inbox

💰 Token
/token supply – Total SLH supply
/token balance – Your SLH balance
/token send <user_id> <amount> – Send SLH
/token_wizard – Wallet setup guide

💰 Economy & Payments
/balance – Check your balance
/buy – Purchase items/credits
/pay – Make a payment

🛒 Marketplace
/market – Browse plugins
/market_installed – Your installed
/market_search <term> – Search
/market_rate <id> <rating> – Rate

🎮 Demo
/demo – Interactive demo menu
/demo agents – Demo agents
/demo tasks – Demo tasks
/demo guide – Quick guide

💬 Ask & Help
/ask <question> – Ask SLH AI
/help – This menu

🗑 My Junk
/my_junk – Your junk items

🏆 Leaderboard
/leaderboard – Top learners

👤 Account
/user – Your profile info

Admins: use /admin for system controls.
""")
