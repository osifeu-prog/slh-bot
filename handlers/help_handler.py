def register(bot):
    @bot.message_handler(commands=['help'])
    def help_cmd(msg):
        text = """נ“˜ SLH Commands

נ‘₪ Account
/start ג€“ Welcome
/join ג€“ Register
/me ג€“ Your profile
/profile ג€“ Detailed profile

נ“ Learning
/courses ג€“ List courses
/course_slh ג€“ SLH course
/lesson ג€“ Start lesson
/finish ג€“ Finish lesson
/progress ג€“ Your progress
/map ג€“ Learning map

נ₪– Agents
/agents ג€“ List agents
/agent_create <name> ג€“ Create agent
/agent_delete <id> ג€“ Delete agent
/agentstate <prefix> <state> ג€“ Set state
/sendagent <prefix> <msg> ג€“ Send message
/inbox <prefix> ג€“ Check inbox

נ’° Economy
/balance ג€“ Check balance
/pay ג€“ Make payment
/buy ג€“ Purchase items
/revenue ג€“ Revenue status

נ“‹ Tasks & Missions
/task ג€“ Manage tasks
/task_add ג€“ Add task
/mission ג€“ Mission control
/complete ג€“ Mark complete

נ—³ Voting
/vote <id> <yes/no> ג€“ Vote
/propose <text> ג€“ Create proposal
/tally <id> ג€“ Show results

נ“¡ Devices
/device_register <name>
/device_list
/device_status <id>
/device_delete <id>
/device_heartbeat

נ† Leaderboard
/top ג€“ Top learners

נ›  Admin
/admin ג€“ Admin panel
/exec  - Shell (admin)
/autoexec - Execute admin command batches
/backup ג€“ Backup DB
/megadiag ג€“ Full diagnostic
/health ג€“ Health check
/status ג€“ System status
/deploy ג€“ Trigger deploy

נ’¬ Ask & Help
/ask <question> ג€“ Ask AI
/help ג€“ This menu
"""
        bot.reply_to(msg, text)






