"""Owner-only business and operations control for SLH MAIN."""
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
import state_manager

MAX_MESSAGE = 3800

def _admin(message):
    from admin_utils import is_admin
    return bool(is_admin(message))

def _iso(value):
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None

def _period_days(message, default=30):
    parts=(message.text or "").split()
    if len(parts)<2: return default
    try: days=int(parts[1])
    except ValueError: return default
    return max(1,min(days,365))

def _users_report(days):
    db=state_manager.load_db()
    users=db.get("users",{})
    users=users if isinstance(users,dict) else {}
    cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    new_users=0
    joined=0
    for user in users.values():
        if not isinstance(user,dict): continue
        if user.get("joined"): joined+=1
        stamp=((user.get("profile") or {}).get("created") or user.get("created_at") or user.get("joined_at"))
        dt=_iso(stamp)
        if dt and dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        if dt and dt>=cutoff: new_users+=1
    return (
        "👥 SLH USERS\n\n"
        f"סה״כ משתמשים: {len(users)}\n"
        f"משתמשים רשומים: {joined}\n"
        f"כניסות חדשות ב־{days} ימים: {new_users}\n\n"
        "מקור: state/db.json (canonical MAIN)."
    )

def _revenue_report(days):
    db=state_manager.load_db()
    rows=db.get("revenue_ledger",[])
    rows=rows if isinstance(rows,list) else []
    cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    period=[]
    for row in rows:
        if not isinstance(row,dict): continue
        dt=_iso(row.get("timestamp"))
        if dt and dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        if dt and dt>=cutoff: period.append(row)
    totals=Counter()
    customers=set()
    for row in period:
        totals[str(row.get("currency","UNKNOWN"))]+=float(row.get("amount",0) or 0)
        if row.get("uid") not in (None,""): customers.add(str(row["uid"]))
    lines=[
        "💰 SLH REVENUE","",
        f"תקופה: {days} ימים",
        f"אירועי הכנסה מאומתים: {len(period)}",
        f"לקוחות משלמים: {len(customers)}",
    ]
    for currency,total in sorted(totals.items()): lines.append(f"• {currency}: {total:g}")
    if not period: lines.append("• כרגע אין אירועי הכנסה מאומתים בתקופה.")
    lines += ["","מקור: revenue_ledger.","הוצאה פנימית של Credits אינה נחשבת להכנסה כספית."]
    return "\n".join(lines)

def _ai_report():
    url=(os.getenv("OLLAMA_BASE_URL") or "").strip()
    model=(os.getenv("OLLAMA_MODEL") or "").strip() or "qwen3:8b"
    lines=[
        "🧠 SLH AI","",
        f"Ollama: {'🟢 configured' if url else '⚪️ not configured'}",
        f"Model: {model}",
        f"Gemini: {'🟢' if (os.getenv('GEMINI_API_KEY') or '').strip() else '⚪️'}",
        f"Groq: {'🟢' if (os.getenv('GROQ_API_KEY') or '').strip() else '⚪️'}",
    ]
    try:
        from core.ai_guard import status
        groq=status().get("groq",{})
        lines.append(f"Groq circuit breaker: failures={groq.get('failures',0)}")
    except Exception:
        lines.append("Groq circuit breaker: unavailable")
    lines += ["", "Ollama endpoint עדיין לא מוגדר ב־MAIN." if not url else "Ollama endpoint מוגדר ב־MAIN; נדרשת בדיקת chat בפועל."]
    return "\n".join(lines)

def _bots_report():
    lines=["🤖 SLH BOT INVENTORY",""]
    seen=set()
    try:
        from core import bot_factory
        from core.identity import OWNER_TELEGRAM_ID
        bots=bot_factory.list_bots(owner_id=str(OWNER_TELEGRAM_ID))
        for item in bots or []:
            key=str(item.get("id") or item.get("name") or "")
            if key in seen: continue
            seen.add(key)
            lines.append(f"• {item.get('name',key)} | {item.get('status','unknown')} | Railway: {item.get('railway','not-bound')}")
    except Exception:
        pass
    if not seen: lines.append("• אין bots רשומים ב־Bot Factory הקנוני.")
    lines += ["","⚠️ Bots חיצוניים אינם נספרים למשתמשים/הכנסות עד שחיבור telemetry מאומת קיים."]
    return "\n".join(lines)

def _registered_bot_count():
    try:
        from core import bot_factory
        from core.identity import OWNER_TELEGRAM_ID
        return len(bot_factory.list_bots(owner_id=str(OWNER_TELEGRAM_ID)) or [])
    except Exception:
        return 0

def _business_summary():
    db=state_manager.load_db()
    users=db.get("users",{}); revenue=db.get("revenue_ledger",[])
    orders=db.get("star_item_orders",{}); vip=db.get("vip_subscriptions",{})
    users=users if isinstance(users,dict) else {}
    revenue=revenue if isinstance(revenue,list) else []
    orders=orders if isinstance(orders,dict) else {}
    vip=vip if isinstance(vip,dict) else {}
    xtr=sum(float(r.get("amount",0) or 0) for r in revenue if isinstance(r,dict) and str(r.get("currency",""))=="XTR")
    active_vip=sum(1 for r in vip.values() if isinstance(r,dict) and str(r.get("status","")).upper()=="ACTIVE")
    fulfilled=sum(1 for r in orders.values() if isinstance(r,dict) and str(r.get("status","")).upper()=="FULFILLED")
    return (
        "📊 SLH BUSINESS CONTROL\n\n"
        f"👥 Users: {len(users)}\n"
        f"💰 Verified revenue: {xtr:g} XTR\n"
        f"🧾 Revenue events: {len(revenue)}\n"
        f"👑 Active VIP: {active_vip}\n"
        f"🛍 Fulfilled Stars orders: {fulfilled}\n"
        f"🤖 Registered bots: {_registered_bot_count()}\n\n"
        "/biz_users [days]\n/biz_revenue [days]\n/biz_ai\n/biz_bots"
    )

def register(bot, context=None):
    @bot.message_handler(commands=["biz","business"])
    def business_cmd(message):
        if not _admin(message): bot.reply_to(message,"⛔️ Admin only"); return
        bot.reply_to(message,_business_summary()[:MAX_MESSAGE])
    @bot.message_handler(commands=["biz_users"])
    def users_cmd(message):
        if not _admin(message): bot.reply_to(message,"⛔️ Admin only"); return
        bot.reply_to(message,_users_report(_period_days(message))[:MAX_MESSAGE])
    @bot.message_handler(commands=["biz_revenue"])
    def revenue_cmd(message):
        if not _admin(message): bot.reply_to(message,"⛔️ Admin only"); return
        bot.reply_to(message,_revenue_report(_period_days(message))[:MAX_MESSAGE])
    @bot.message_handler(commands=["biz_ai"])
    def ai_cmd(message):
        if not _admin(message): bot.reply_to(message,"⛔️ Admin only"); return
        bot.reply_to(message,_ai_report()[:MAX_MESSAGE])
    @bot.message_handler(commands=["biz_bots"])
    def bots_cmd(message):
        if not _admin(message): bot.reply_to(message,"⛔️ Admin only"); return
        bot.reply_to(message,_bots_report()[:MAX_MESSAGE])
    print("✅ business control handler registered")
