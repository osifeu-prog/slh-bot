import telebot
from telebot import types
import json
from datetime import datetime

DB_PATH="state/db.json"

def ensure_onboarding_user(uid):
    uid=str(uid)

    try:
        with open(DB_PATH, encoding="utf-8") as f:
            db=json.load(f)
    except:
        db={"users":{}}

    db.setdefault("users",{})

    if uid not in db["users"]:
        db["users"][uid]={
            "profile":{
                "created":datetime.now().isoformat(),
                "telegram_id":uid
            },
            "wallet":{
                "credits":10
            },
            "academy":{
                "courses":{
                    "bitcoin_mastery":{
                        "stage":1,
                        "completed":[1]
                    }
                }
            },
            "gamification":{
                "points":25,
                "level":1
            },
            "referral":{
                "code":None,
                "count":0,
                "commission":0
            },
            "onboarding":{
                "completed":False,
                "stage":"welcome"
            },
            "ai":{
                "initialized":False
            }
        }

    else:
        db["users"][uid].setdefault("onboarding",{
            "completed":False,
            "stage":"welcome"
        })

    with open(DB_PATH,"w",encoding="utf-8") as f:
        json.dump(db,f,indent=2,ensure_ascii=False)

    return db["users"][uid]


def init(bot):
    @bot.message_handler(commands=['start'])
    def start(m):
        print(
            f"START HANDLER: chat={m.chat.id} "
            f"msg={m.message_id} "
            f"text={repr(m.text)}"
        )
        user=ensure_onboarding_user(m.from_user.id)
        print("ONBOARDING USER:",m.from_user.id)
        try:
            with open("branding/SLH_LOGO.txt", "r", encoding="utf-8") as lf:
                logo = lf.read()
            bot.send_message(m.chat.id, f"```\n{logo}\n```", parse_mode="Markdown")
        except Exception as e:
            print("logo error:", e)
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            ("🚀 התחלת מערכת", "onboarding_start"),
            ("📚 קורסים", "start_courses"),
            ("🤖 סוכנים", "start_agents"),
            ("💰 יתרה", "start_balance"),
            ("📘 עזרה", "start_help"),
            ("❓ שאלה", "start_ask"),
            ("🛠 אדמין", "start_admin")
        ]
        for text, callback in buttons:
            markup.add(types.InlineKeyboardButton(text, callback_data=callback))
        text = """**ברוך הבא ל-SLH OS!** 🚀

מערכת הפעלה חכמה – קורסים, סוכני AI, השקעות, וכלכלה דיגיטלית.

✅ **הכל כבר פה** – אין צורך להמציא כלום.
✅ **התחל** בכפתורים למטה, או שלח /help לכל הפקודות.

💡 **טיפ**: /ask <שאלה> – אני אעזור לך."""
        bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('start_'))
    def start_callback(call):
        mapping = {
            "courses": "📚 קורסים זמינים – /courses",
            "agents": "🤖 סוכנים – /agents",
            "balance": "💰 יתרה – /balance",
            "help": "📘 עזרה – /help",
            "ask": "❓ שלח /ask <שאלה>",
            "admin": "🛠 אדמין – /admin"
        }
        key = call.data.replace('start_', '')
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            mapping.get(key, "❓ בחר אפשרות"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )

