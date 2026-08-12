def register(bot):
    @bot.message_handler(commands=['help'])
    def help_cmd(msg):
        text = """׳ ֲג€ֻ SLH Commands

׳ ֲג€˜ג‚× Account
/start ׳’ג‚¬ג€ Welcome
/join ׳’ג‚¬ג€ Register
/me ׳’ג‚¬ג€ Your profile
/profile ׳’ג‚¬ג€ Detailed profile

׳ ֲג€ֲ Learning
/courses ׳’ג‚¬ג€ List courses
/course_slh ׳’ג‚¬ג€ SLH course
/lesson ׳’ג‚¬ג€ Start lesson
/finish ׳’ג‚¬ג€ Finish lesson
/progress ׳’ג‚¬ג€ Your progress
/map ׳’ג‚¬ג€ Learning map

׳ ֲג‚×ג€“ Agents
/agents ׳’ג‚¬ג€ List agents
/agent_create <name> ׳’ג‚¬ג€ Create agent
/agent_delete <id> ׳’ג‚¬ג€ Delete agent
/agentstate <prefix> <state> ׳’ג‚¬ג€ Set state
/sendagent <prefix> <msg> ׳’ג‚¬ג€ Send message
/inbox <prefix> ׳’ג‚¬ג€ Check inbox

׳ ֲג€™ֲ° Economy
/balance ׳’ג‚¬ג€ Check balance
/pay ׳’ג‚¬ג€ Make payment
/buy ׳’ג‚¬ג€ Purchase items
/revenue ׳’ג‚¬ג€ Revenue status

׳ ֲג€ג€¹ Tasks & Missions
/task ׳’ג‚¬ג€ Manage tasks
/task_add ׳’ג‚¬ג€ Add task
/mission ׳’ג‚¬ג€ Mission control
/complete ׳’ג‚¬ג€ Mark complete

׳ ֲג€”ֲ³ Voting
/vote <id> <yes/no> ׳’ג‚¬ג€ Vote
/propose <text> ׳’ג‚¬ג€ Create proposal
/tally <id> ׳’ג‚¬ג€ Show results

׳ ֲג€ֲ¡ Devices
/device_register <name>
/device_list
/device_status <id>
/device_delete <id>
/device_heartbeat

׳ ֲֲג€  Leaderboard
/top ׳’ג‚¬ג€ Top learners

׳ ֲג€÷ֲ  Admin
/admin ׳’ג‚¬ג€ Admin panel
/exec  - Shell (admin)
/autoexec - Execute admin command batches
/backup ׳’ג‚¬ג€ Backup DB
/megadiag ׳’ג‚¬ג€ Full diagnostic
/health ׳’ג‚¬ג€ Health check
/status ׳’ג‚¬ג€ System status
/deploy ׳’ג‚¬ג€ Trigger deploy

׳ ֲג€™ֲ¬ Ask & Help
/ask <question> ׳’ג‚¬ג€ Ask AI
/help ׳’ג‚¬ג€ This menu
"""
        bot.reply_to(msg, text[:4000])







