from core.authority import is_owner
import json, os, subprocess, glob, tempfile, time


# Curated diagnostics only. Keep every command single-line and read-only.
OPS_CLIP_ITEMS = {
    "gates": {
        "label": "בדיקת שערי הפקדות",
        "command": "/e python3 -c 'import os; from core.bnb_gate import bnb_readiness,bnb_deposits_open,bnb_settlement_allowed; from core.ton_deposit_service import _deposits_open as ton_open; r=bnb_readiness(); print(\"BNB_FLAG\",r.get(\"flag_open\"),\"BNB_PUBLIC\",bnb_deposits_open(),\"CANARY_CONFIGURED\",bool(os.getenv(\"BNB_DEPOSITS_CANARY_UID\",\"\" ).strip()),\"PROBE\",bnb_settlement_allowed(\"__slh_readonly_probe__\")); print(\"TON_PUBLIC\",ton_open(),\"TON_ENV\",os.getenv(\"TON_DEPOSITS_OPEN\"),\"SLH_FLAG\",os.getenv(\"SLH_DEPOSITS_OPEN\"))'",
    },
    "counts": {
        "label": "ספירת Ledger",
        "command": "/e python3 -c \"import json; d=json.load(open('state/db.json',encoding='utf-8')); L=d.get('ledger',[]); print('bnb:deposit',sum(1 for e in L if e.get('reason')=='bnb:deposit'),'ton:deposit',sum(1 for e in L if e.get('reason')=='ton:deposit')); print('slh_onchain',sum(1 for e in d.get('slh_token_ledger',[]) if e.get('reason')=='onchain:deposit:slh')); print('wallet_bindings',len(d.get('wallet_bindings',{})),'ton_bindings',len(d.get('ton_wallet_bindings',{})),'withdrawals',len(d.get('withdrawal_requests',{})))\"",
    },
    "deposits": {
        "label": "פרטי הפקדות — UID ו־TX מקוצרים",
        "command": "/e python3 -c \"import json; d=json.load(open('state/db.json',encoding='utf-8')); L=d.get('ledger',[]); [print(str(e.get('time',e.get('timestamp','')))[:19],e.get('reason'),'uid...'+str(e.get('uid',''))[-4:],'amount=',e.get('amount'),'tx...'+str((e.get('meta') or {}).get('tx_hash',''))[-8:]) for e in L if e.get('reason') in ('bnb:deposit','ton:deposit')]; [print(str(e.get('timestamp',''))[:19],e.get('reason'),'uid...'+str(e.get('to_uid',''))[-4:],'amount=',e.get('amount'),'tx...'+str(e.get('tx_hash',''))[-8:]) for e in d.get('slh_token_ledger',[]) if e.get('reason')=='onchain:deposit:slh']\"",
    },
    "exchange": {
        "label": "מצב שער Exchange",
        "command": "/e python3 -c 'import os; from core.exchange_gate import public_open; print(\"EXCHANGE_PUBLIC_GATE\",public_open(),\"ENV\",os.getenv(\"SLH_EXCHANGE_PUBLIC_OPEN\"))'",
    },
}

def register(bot, context):
    @bot.message_handler(commands=['health'])
    def health(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔️ OWNER only")
            return
        try:
            with open('state/db.json') as f:
                d = json.load(f)
            users = len(d.get('users', {}))
            agents = len(d.get('agents', {}))
            bot.reply_to(m, f"✅ Health OK – Users: {users}, Agents: {agents}")
        except:
            bot.reply_to(m, "❌ DB check failed")

    @bot.message_handler(commands=['status'])
    def status(m):
        env = os.environ.get("RAILWAY_ENVIRONMENT", "local")
        bot.reply_to(m, f"🟢 SLH Bot Online | Railway: {env} | /admin for more")

    @bot.message_handler(commands=['megadiag'])
    def megadiag(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔️ OWNER only")
            return
        lines = ["📊 MEGA DIAGNOSTICS", ""]
        lines.append("Disk usage:")
        try:
            import shutil
            total, used, free = shutil.disk_usage("/app" if os.path.isdir("/app") else ".")
            lines.append(f"  Total: {total//1024//1024} MB, Used: {used//1024//1024} MB, Free: {free//1024//1024} MB")
        except:
            lines.append("  (not available)")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=['backup'])
    def backup(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔️ OWNER only")
            return
        try:
            with open('state/db.json', 'rb') as f:
                bot.send_document(m.chat.id, f, visible_file_name='db_backup.json')
        except Exception as e:
            bot.reply_to(m, f"❌ Backup failed: {e}")

    @bot.message_handler(commands=['clean'])
    def clean(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔️ OWNER only")
            return
        patterns = ['*.pyc', '__pycache__']
        count = 0
        for pattern in patterns:
            for f in glob.glob(f'**/{pattern}', recursive=True):
                try:
                    if os.path.isdir(f):
                        os.rmdir(f)
                    else:
                        os.remove(f)
                    count += 1
                except:
                    pass
        bot.reply_to(m, f"🧹 Cleaned {count} temp files")

    @bot.message_handler(commands=['results'])
    def results(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔️ OWNER only")
            return
        bot.reply_to(m, "🗳 No active vote. (voting engine not connected)")

    @bot.message_handler(commands=["opsclip"])
    def opsclip_menu(message):
        """Owner-only manual menu of short, read-only commands to copy in Telegram."""
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if not is_owner(uid):
            bot.reply_to(message, "⛔️ OWNER only")
            return
        chat_type = str(getattr(getattr(message, "chat", None), "type", "") or "").lower()
        if chat_type != "private":
            bot.reply_to(message, "פתח שיחה פרטית עם הבוט והרץ /opsclip")
            return

        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("בדיקת שערים", callback_data="opsclip:gates"),
            InlineKeyboardButton("מונה Ledger", callback_data="opsclip:counts"),
            InlineKeyboardButton("פרטי הפקדות", callback_data="opsclip:deposits"),
            InlineKeyboardButton("שער Exchange", callback_data="opsclip:exchange"),
        )
        bot.reply_to(
            message,
            "🧰 SLH OPS CLIPBOARD — READ ONLY\n"
            "בחר פקודה; הבוט ישלח אותה בהודעה נפרדת ונוחה להעתקה.\n"
            "הפקודות אינן מפעילות settlement או משנות נתונים.",
            reply_markup=markup,
        )

    @bot.callback_query_handler(func=lambda call: str(getattr(call, "data", "") or "").startswith("opsclip:"))
    def opsclip_send_command(call):
        """Return only a pre-approved, single-line diagnostic command."""
        uid = str(getattr(getattr(call, "from_user", None), "id", "") or "")
        message = getattr(call, "message", None)
        chat = getattr(message, "chat", None)
        chat_type = str(getattr(chat, "type", "") or "").lower()
        chat_id = getattr(chat, "id", None)
        if not is_owner(uid) or chat_type != "private" or chat_id is None:
            bot.answer_callback_query(call.id, "Owner private chat only", show_alert=True)
            return

        key = str(getattr(call, "data", "") or "").split(":", 1)[1]
        item = OPS_CLIP_ITEMS.get(key)
        if not item:
            bot.answer_callback_query(call.id, "פקודה לא מוכרת", show_alert=True)
            return

        from html import escape
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"📋 {item['label']} — להעתקה:\n<pre>{escape(item['command'], quote=False)}</pre>",
            parse_mode="HTML",
        )

    print("✅ admin_extras loaded")

