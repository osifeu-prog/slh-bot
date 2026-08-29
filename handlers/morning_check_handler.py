import json
from pathlib import Path
from datetime import datetime

def register(bot, context=None):
    @bot.message_handler(commands=["morning_check"])
    def morning_check(m):
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        lines = ["🌅 דוח פתיחת יום SLH", f"🕒 {now}", ""]

        # 1. Doctor
        try:
            from doctor_handler import generate_health_report
            doctor = generate_health_report(bot)
            lines.append("🩺 בריאות המערכת:")
            lines.append(doctor)
        except Exception as e:
            lines.append(f"❌ doctor error: {e}")

        lines.append("")

        # 2. Missions
        try:
            from core.mission_lifecycle import MissionLifecycleService
            service = MissionLifecycleService(".")
            board, _ = service.load_state()
            missions = board.get("missions", [])
            open_missions = [m for m in missions if m.get("status") == "open"]
            assigned_missions = [m for m in missions if m.get("assigned_to") not in (None, "")]
            lines.append("📋 משימות:")
            lines.append(f"   פתוחות: {len(open_missions)}")
            lines.append(f"   משויכות: {len(assigned_missions)}")
            for m in missions[:5]:
                lines.append(f"   - {m.get('id')} [{m.get('status')}]")
        except Exception as e:
            lines.append(f"❌ missions error: {e}")

        lines.append("")

        # 3. Balance
        try:
            from core import economy_service
            bal = economy_service.get_balance_safe(str(m.from_user.id))
            staked = economy_service.get_staked_safe(str(m.from_user.id))
            lines.append(f"💰 יתרה: {bal}")
            lines.append(f"🔒 סטייקינג: {staked}")
        except Exception as e:
            lines.append(f"❌ balance error: {e}")

        lines.append("")

        # 4. Devices
        try:
            devices = json.loads(Path("state/devices.json").read_text(encoding="utf-8")).get("devices", {})
            online = sum(1 for d in devices.values() if d.get("status") == "online")
            lines.append(f"📡 מכשירים: {len(devices)} ({online} online)")
        except Exception as e:
            lines.append(f"❌ devices error: {e}")

        lines.append("")
        lines.append("✅ סיכום בוקר הושלם")

        chat_id = None

        if isinstance(m, dict):
            chat_id = m.get("chat", {}).get("id")
        elif hasattr(m, "chat"):
            chat_id = m.chat.id

        if chat_id:
            bot.send_message(chat_id, "\n".join(lines))
