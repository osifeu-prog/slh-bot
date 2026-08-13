import subprocess
import time
import uuid
from telebot import types
import state_manager
from core import profile_manager
from core.identity import OWNER_TELEGRAM_ID

def register(bot):
    @bot.message_handler(commands=['execr'])
    def execr(m):
        uid = str(m.from_user.id)
        from security.permissions import has_permission
        if not has_permission(uid, 'exec_request'):
            bot.reply_to(m, "⛔ אין לך הרשאת exec_request")
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /execr <command>")
            return
        cmd = parts[1]

        request_id = str(uuid.uuid4())[:8]

        def mutate(db):
            pending = db.setdefault('pending_exec', {})
            pending[request_id] = {
                'id': request_id,
                'uid': uid,
                'command': cmd,
                'status': 'pending',
                'created_at': time.time()
            }
            return request_id
        state_manager.atomic_update(mutate)

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ אשר", callback_data=f"approve_exec_{request_id}"),
            types.InlineKeyboardButton("❌ דחה", callback_data=f"reject_exec_{request_id}")
        )
        bot.send_message(
            OWNER_TELEGRAM_ID,
            f"🛡 בקשת הרשאת פקודה\n"
            f"👤 מפתח: {uid}\n"
            f"💻 פקודה: {cmd}\n"
            f"🔑 ID: {request_id}",
            reply_markup=markup
        )
        bot.reply_to(m, f"⏳ בקשתך נשלחה לאישור OWNER.\n🔑 ID: {request_id}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_exec_', 'reject_exec_')))
    def handle_exec_decision(call):
        if call.from_user.id != OWNER_TELEGRAM_ID:
            bot.answer_callback_query(call.id, "⛔ OWNER only")
            return

        if call.data.startswith('approve_exec_'):
            action = 'approve'
            request_id = call.data[len('approve_exec_'):]
        else:
            action = 'reject'
            request_id = call.data[len('reject_exec_'):]

        db = state_manager.load_db()
        pending = db.get('pending_exec', {}).get(request_id)
        if not pending or pending['status'] != 'pending':
            bot.answer_callback_query(call.id, "❌ הבקשה לא פעילה")
            return

        pending['status'] = 'approved' if action == 'approve' else 'rejected'
        pending['decided_by'] = str(call.from_user.id)
        pending['decided_at'] = time.time()
        db['pending_exec'][request_id] = pending
        db.setdefault('exec_audit', []).append(pending.copy())
        state_manager.save_db(db)

        if action == 'approve':
            bot.answer_callback_query(call.id, "✅ אושר, מריץ פקודה")
            try:
                result = subprocess.run(pending['command'], shell=True, capture_output=True, text=True, timeout=15)
                output = (result.stdout + result.stderr).strip()
                if not output:
                    output = "(no output)"
                if len(output) > 4000:
                    output = output[:4000] + "\n... truncated"
                bot.send_message(pending['uid'], f"✅ פקודה אושרה ורצה:\n{pending['command']}\n\nפלט:\n{output}")
                bot.send_message(OWNER_TELEGRAM_ID, f"✅ פלט הפקודה עבור {pending['uid']}:\n{output}")
            except Exception as e:
                err = f"❌ שגיאה בהרצה: {e}"
                bot.send_message(pending['uid'], err)
                bot.send_message(OWNER_TELEGRAM_ID, err)
        else:
            bot.answer_callback_query(call.id, "❌ נדחה")
            bot.send_message(pending['uid'], f"❌ בקשתך נדחתה על ידי OWNER.\nפקודה: {pending['command']}")
