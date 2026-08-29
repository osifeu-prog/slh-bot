from core.identity import OWNER_TELEGRAM_ID

def init(bot):
    @bot.message_handler(commands=['admin'])
    def admin_panel(message):
        if int(message.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(message, "⛔️ OWNER only")
            return
        text = """🔧 ADMIN CONTROL PANEL**

🩺 **DIAGNOSTICS
/doctor – Full health report
/megadiag – Mega diagnostics
/status – System status
/health – Health check
/diagnose – Diagnostic

💰 ECONOMY
/balance – Check balance
/pay – Buy credits
/revenue – Revenue status
/stake – Stake credits
/unstake – Unstake credits
/airdrop – Send airdrop
/claim – Claim BNB deposit

🗳 GOVERNANCE
/propose – Create proposal
/vote – Vote yes/no
/tally – Show proposal result
/gov_status – Governance status
/session_new – New session
/session_close – Close session

🎯 MISSIONS & PROGRESS
/mission – Mission control
/task – Manage tasks
/progress – Your progress
/worklog – Work log

🤖 AGENTS & AI
/agents – List agents
/agent_create – Create agent
/register_ai – Register AI agents
/sendagent – Send to agent
/inbox – Agent inbox

🛠 SYSTEM & DEV
/deploy – Trigger Railway deploy
/git commit – Git commit
/backup – Backup DB
/exec – Execute command
/execr – Request approval
/autoexec – Batch execute
/logs – Recent logs
/clean – Clean temp
/sysinfo – System resources
/disk – Disk usage

🌐 UI & NAVIGATION
/miniapp – Open Mini App
/dashboard – Dashboard
/help – Help menu

📌 עקרונות
כל פעולה רגישה עוברת דרך core.exec_policy.run_gated.
אין גישה ישירה ל-state או subprocess.
"""
        bot.reply_to(message, text, parse_mode="Markdown")
