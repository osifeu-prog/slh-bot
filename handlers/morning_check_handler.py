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
            from handlers.doctor_handler import generate_health_report
            doctor = generate_health_report(bot)
            lines.append("🩺 בריאות המערכת:")
            lines.append(str(doctor)[:800])
        except Exception:
            lines.append("🩺 בריאות המערכת: /doctor זמין")

        lines.append("")

        # 2. Missions
        try:
            from core.mission_lifecycle import MissionLifecycleService
            service = MissionLifecycleService(".")
            board, _ = service.load_state()
            missions = board.get("missions", [])
            open_m = [x for x in missions if x.get("status") == "open"]
            assigned_m = [x for x in missions if x.get("assigned_to") not in (None, "")]
            lines.append("📋 משימות:")
            lines.append(f"   פתוחות: {len(open_m)}")
            lines.append(f"   משויכות: {len(assigned_m)}")
            for miss in missions[:5]:
                lines.append(f"   - {miss.get('id')} [{miss.get('status')}]")
        except Exception as e:
            lines.append(f"❌ missions error: {e}")

        lines.append("")

        # 3. Balance
        try:
            from core import economy_service
            uid = str(m.from_user.id)
            bal = economy_service.get_balance_safe(uid)
            staked = economy_service.get_staked_safe(uid)
            lines.append(f"💰 יתרה: {bal}")
            lines.append(f"🔒 סטייקינג: {staked}")
        except Exception as e:
            lines.append(f"❌ balance error: {e}")

        lines.append("")

        # 4. Devices
        try:
            dev_path = Path("state/devices.json")
            if dev_path.exists():
                devices = json.loads(dev_path.read_text(encoding="utf-8")).get("devices", {})
                online = sum(1 for d in devices.values() if d.get("status") == "online")
                lines.append(f"📡 מכשירים: {len(devices)} ({online} online)")
            else:
                lines.append("📡 מכשירים: אין קובץ devices.json")
        except Exception as e:
            lines.append(f"❌ devices error: {e}")

        lines.append("")
        lines.append("✅ סיכום בוקר הושלם")

        chat_id = getattr(getattr(m, "chat", None), "id", None)
        if chat_id is None and isinstance(m, dict):
            chat_id = m.get("chat", {}).get("id")
        if chat_id:
            bot.send_message(chat_id, "\n".join(lines))
        else:
            bot.reply_to(m, "\n".join(lines))
