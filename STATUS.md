# SLH Learning System – Status
## Generated: $(date)
- **Bot**: Running
- **Database**: db.json (SQLite-like JSON)
- **Modules**: learn_handlers, project_commands, smart_leaderboard, welcome_handler (inline)
- **Features**:
  - /start – Welcome message (Hebrew)
  - /join – Student registration
  - /courses, /task, /submit, /myprogress – Course management
  - /project create/open/task/status/agent – Personal projects
  - /leaderboard – Smart leaderboard with projects/agents
  - /vote, /lost – Community engagement
  - /pay, /referral, /activate, /commission – Affiliate system
  - /diagnose, /check – System health
  - /exec – Admin shell
- **Backups**: Git auto-backup via /backup
- **Admin IDs**: $(python3 -c "import json;print(json.load(open('db.json'))['admins'])")
