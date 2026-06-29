import os, shutil, json, datetime

PROJECTS_ROOT = os.path.expanduser("~/slh_clean/projects")

def init(bot):
    @bot.message_handler(commands=['project'])
    def handle_project(m):
        args = m.text.split()
        if len(args) < 2:
            bot.reply_to(m, "Usage: /project create/list/open/status/roadmap/task/agent/backup")
            return
        cmd = args[1].lower()
        uid = str(m.chat.id)

        if cmd == 'create':
            if len(args) < 3:
                bot.reply_to(m, "Usage: /project create <name>")
                return
            name = args[2]
            project_path = os.path.join(PROJECTS_ROOT, name)
            if os.path.exists(project_path):
                bot.reply_to(m, f"❌ Project {name} already exists.")
                return
            try:
                os.makedirs(project_path, exist_ok=True)
                for folder in ['vision','roadmap','tasks','agents','memory','knowledge','decisions','status','deploy','logs']:
                    os.makedirs(os.path.join(project_path, folder), exist_ok=True)
                with open(os.path.join(project_path, 'owner.txt'), 'w') as f:
                    f.write(uid)
                bot.reply_to(m, f"✅ Project {name} created successfully!")
            except Exception as e:
                bot.reply_to(m, f"❌ Error: {e}")

        elif cmd == 'list':
            if not os.path.exists(PROJECTS_ROOT):
                bot.reply_to(m, "📭 No projects yet.")
                return
            projects = [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]
            if not projects:
                bot.reply_to(m, "📭 No projects found.")
            else:
                msg = "📁 **Projects:**\n" + "\n".join(f"• {p}" for p in projects)
                bot.reply_to(m, msg, parse_mode="Markdown")

        elif cmd == 'open':
            if len(args) < 3:
                bot.reply_to(m, "Usage: /project open <name>")
                return
            name = args[2]
            project_path = os.path.join(PROJECTS_ROOT, name)
            if not os.path.exists(project_path):
                bot.reply_to(m, f"❌ Project {name} not found.")
                return
            owner_file = os.path.join(project_path, 'owner.txt')
            if os.path.exists(owner_file):
                with open(owner_file) as f:
                    owner = f.read().strip()
                if owner != uid:
                    bot.reply_to(m, "❌ You are not the owner of this project.")
                    return
            db = json.load(open("db.json"))
            db.setdefault("active_projects", {})[uid] = name
            json.dump(db, open("db.json", "w"), indent=2)
            bot.reply_to(m, f"✅ Active project set to {name}")

        elif cmd == 'status':
            db = json.load(open("db.json"))
            active = db.get("active_projects", {}).get(uid)
            if not active:
                bot.reply_to(m, "❌ No active project. Use /project open <name>")
                return
            tasks_file = os.path.join(PROJECTS_ROOT, active, 'tasks', 'TASKS.md')
            if os.path.exists(tasks_file):
                with open(tasks_file) as f:
                    lines = f.readlines()
                total = len([l for l in lines if l.strip().startswith('- [ ]') or l.strip().startswith('- [x]')])
                done = len([l for l in lines if l.strip().startswith('- [x]')])
                msg = f"📊 {active}: {done}/{total} tasks completed"
            else:
                msg = f"📊 {active}: No tasks defined yet."
            bot.reply_to(m, msg)

        elif cmd == 'task':
            if len(args) < 4 or args[2] != 'add':
                bot.reply_to(m, "Usage: /project task add <description>")
                return
            db = json.load(open("db.json"))
            active = db.get("active_projects", {}).get(uid)
            if not active:
                bot.reply_to(m, "❌ No active project.")
                return
            desc = ' '.join(args[3:])
            tasks_file = os.path.join(PROJECTS_ROOT, active, 'tasks', 'TASKS.md')
            with open(tasks_file, 'a') as f:
                f.write(f"- [ ] {desc}\n")
            bot.reply_to(m, f"✅ Task added to {active}")

        elif cmd == 'agent':
            if len(args) < 4 or args[2] != 'add':
                bot.reply_to(m, "Usage: /project agent add <agent_name>")
                return
            db = json.load(open("db.json"))
            active = db.get("active_projects", {}).get(uid)
            if not active:
                bot.reply_to(m, "❌ No active project.")
                return
            agent_name = args[3]
            agents_file = os.path.join(PROJECTS_ROOT, active, 'agents', 'AGENTS.md')
            with open(agents_file, 'a') as f:
                f.write(f"- {agent_name}\n")
            bot.reply_to(m, f"✅ Agent {agent_name} linked to {active}")

        elif cmd == 'roadmap':
            db = json.load(open("db.json"))
            active = db.get("active_projects", {}).get(uid)
            if not active:
                bot.reply_to(m, "❌ No active project.")
                return
            roadmap_file = os.path.join(PROJECTS_ROOT, active, 'roadmap', 'ROADMAP.md')
            if os.path.exists(roadmap_file):
                with open(roadmap_file) as f:
                    content = f.read()
                bot.reply_to(m, f"🗺 Roadmap for {active}:\n{content}")
            else:
                bot.reply_to(m, "📭 Roadmap is empty.")

        elif cmd == 'backup':
            db = json.load(open("db.json"))
            active = db.get("active_projects", {}).get(uid)
            if not active:
                bot.reply_to(m, "❌ No active project.")
                return
            backup_root = os.path.expanduser("~/slh_clean/backups")
            os.makedirs(backup_root, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_root, f"{active}_{timestamp}")
            shutil.copytree(os.path.join(PROJECTS_ROOT, active), backup_path)
            bot.reply_to(m, f"✅ Project backed up to backups/{active}_{timestamp}")

        else:
            bot.reply_to(m, "❌ Unknown subcommand. Use create/list/open/status/roadmap/task/agent/backup")
