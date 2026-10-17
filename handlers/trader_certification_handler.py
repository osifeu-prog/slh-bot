"""Interactive server-recorded test required before internal SLH trading."""
from __future__ import annotations
import secrets
from datetime import datetime, timezone
import state_manager
from core import academy_manager, lesson_engine
from core.trader_certification import (
    TRADER_CERTIFICATION_STAGE, TRADER_COURSE_ID, TRADER_PASS_SCORE,
    TRADER_QUIZ_VERSION, has_trader_certification,
)

QUESTIONS = [
 {"question":"מה מוכיחה עסקה ב-SLH Exchange הפנימי?","options":["שהמחיר זהה בהכרח ל-DEX","שהתבצעה התאמה פנימית לפי ספר הפקודות והיתרות; לא הוכחה למחיר חיצוני","שהכסף ניתן למשיכה לבנק"],"correct":1,"critical":True},
 {"question":"קניית 10 SLH במחיר מרבי של 2 Credits ליחידה: מה נכון?","options":["עד 20 Credits עשויים להידרש לרזרבה; אין הבטחת ביצוע מלא","נדרשים בדיוק 2 Credits לכל העסקה","המערכת מבטיחה קנייה של כל 10 היחידות"],"correct":0,"critical":True},
 {"question":"פקודת הקנייה עדיין פתוחה. מה עושים?","options":["שולחים אותה שוב מיד","מניחים שהעסקה כבר הושלמה","בודקים מצב, כמות שנותרה ואסמכתה; פקודה פתוחה אינה עסקה שהושלמה"],"correct":2,"critical":True},
 {"question":"היתרה או תוצאת העסקה נראות שגויות. מה נכון?","options":["ממשיכים לסחור כדי לאזן את החשבון","עוצרים, שומרים אסמכתה ומדווחים לבדיקת המערכת","משנים יתרה ידנית"],"correct":1,"critical":True},
 {"question":"מה עשויה לעשות הוראת מכירה בספר הפקודות?","options":["לשריין SLH זמין עד לביצוע או לביטול","להבטיח קונה במחיר המבוקש","להעלות את מחיר השוק"],"correct":0,"critical":False},
 {"question":"איך מטפלים בהוראה פתוחה ששייכת לך?","options":["מוחקים היסטוריית עסקאות","שולחים שוב את הוראת המכירה","מזהים את מספר ההוראה ומשתמשים ב-/cancel לאחר בדיקה"],"correct":2,"critical":False},
 {"question":"מה הסיכון כשיש מעט נזילות בספר הפקודות?","options":["אי אפשר לשנות מחיר","פקודה עלולה להתבצע חלקית או להשפיע יותר על המחיר הפנימי","כל הוראה מתבצעת מיד"],"correct":1,"critical":True},
 {"question":"האם המחיר הפנימי מבטיח מחיר זהה למסחר חיצוני?","options":["כן, תמיד","רק אחרי ארבע עסקאות","לא; אלה מקורות שוק ונזילות נפרדים"],"correct":2,"critical":True},
 {"question":"בדיקת השער או ה-runtime נכשלת. מה עושים?","options":["מנסים לעקוף את החסימה","עוצרים, בודקים את קוד החסימה ולא עוקפים אותה","מנסים סכום אחר עד שהפקודה עוברת"],"correct":1,"critical":True},
 {"question":"מהי התנהלות שוק אחראית?","options":["לתאם עסקאות מלאכותיות כדי ליצור רושם ביקוש","להבטיח לאחרים שהמחיר יעלה","לנהל סיכון, לא להבטיח תשואה ולא לתאם פעילות מטעה"],"correct":2,"critical":True},
]

def _now():
    return datetime.now(timezone.utc).isoformat()

def _markup(uid, session_id, index):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=1)
    for choice, option in enumerate(QUESTIONS[index]["options"]):
        markup.add(InlineKeyboardButton(option, callback_data=f"slhcert:{uid}:{session_id}:{index}:{choice}"))
    return markup

def _send_question(bot, chat_id, uid, session_id, index, message_id=None):
    text = (
        f"🎓 מבחן הסמכת סוחר SLH · שאלה {index + 1}/{len(QUESTIONS)}\n\n"
        f"{QUESTIONS[index]['question']}\n\n"
        "נדרש ציון 8/10 לפחות ומעבר של כל שאלות הבטיחות."
    )
    markup = _markup(uid, session_id, index)
    if message_id is not None:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup)

def register(bot):
    @bot.message_handler(commands=["trader_test"])
    def trader_test(message):
        uid = str(message.from_user.id)
        if str(getattr(getattr(message, "chat", None), "type", "")).lower() != "private":
            bot.reply_to(message, "🔒 את מבחן הסמכת הסוחר אפשר לבצע רק בפרטי עם הבוט.")
            return
        try:
            db = state_manager.load_db()
        except Exception:
            bot.reply_to(message, "⛔ מצב ההכשרה אינו זמין כרגע. לא נוצר מבחן.")
            return
        if has_trader_certification(uid, db):
            bot.reply_to(message, "✅ ההסמכה שלך כבר בתוקף. פתח /chart לבורסה הפנימית.")
            return
        try:
            allowed = lesson_engine.has_course_access(uid, TRADER_COURSE_ID)
        except Exception:
            allowed = False
        if not allowed:
            bot.reply_to(message,
                "🔒 הקורס אינו פתוח לחשבונך. שלח /share לקבלת קישור אישי; "
                "הטבת 15 הראשונים מוענקת אחרי שהצטרפות חדשה דרך הקישור הושלמה. "
                "אפשר גם לרכוש: /buystars course_algo_trading.")
            return
        progress = academy_manager.get_course(uid, TRADER_COURSE_ID) or {}
        completed = set()
        for item in progress.get("completed", []) or []:
            try:
                completed.add(int(item))
            except (TypeError, ValueError):
                pass
        if not set(range(1, TRADER_CERTIFICATION_STAGE)).issubset(completed):
            bot.reply_to(message,
                "🔒 לפני המבחן יש להשלים את ששת השיעורים הראשונים לפי הסדר. "
                "המשך דרך /courses ואז /course_algo_trading_999.")
            return
        session_id = secrets.token_hex(4)
        created = _now()
        def create(db):
            sessions = db.setdefault("trader_certification_sessions", {})
            sessions[uid] = {"session_id":session_id,"status":"IN_PROGRESS",
                "quiz_version":TRADER_QUIZ_VERSION,"answers":[],"started_at":created}
            return True
        try:
            state_manager.atomic_update(create)
        except Exception:
            bot.reply_to(message, "⛔ לא ניתן לשמור את המבחן. הרשאת המסחר לא השתנתה.")
            return
        bot.send_message(message.chat.id,
            "🧠 מבחן הכשירות מתחיל: 10 שאלות; נדרשים 8/10 וכל שאלות הבטיחות. "
            "אין כאן הבטחה לרווח או ליציבות מחיר.")
        _send_question(bot, message.chat.id, uid, session_id, 0)

    @bot.callback_query_handler(func=lambda call: str(getattr(call, "data", "")).startswith("slhcert:"))
    def answer_trader_test(call):
        parts = str(call.data or "").split(":")
        if len(parts) != 5:
            bot.answer_callback_query(call.id, "מזהה תשובה לא תקין", show_alert=True)
            return
        _, target_uid, session_id, index_raw, choice_raw = parts
        uid = str(getattr(getattr(call, "from_user", None), "id", "") or "")
        if uid != target_uid:
            bot.answer_callback_query(call.id, "המבחן שייך למשתמש אחר", show_alert=True)
            return
        try:
            index, choice = int(index_raw), int(choice_raw)
        except (TypeError, ValueError):
            bot.answer_callback_query(call.id, "תשובה לא תקינה", show_alert=True)
            return
        if index < 0 or index >= len(QUESTIONS) or choice not in range(len(QUESTIONS[index]["options"])):
            bot.answer_callback_query(call.id, "תשובה מחוץ לטווח", show_alert=True)
            return
        timestamp = _now()
        def record(db):
            sessions = db.get("trader_certification_sessions", {})
            session = sessions.get(uid) if isinstance(sessions, dict) else None
            if not isinstance(session, dict) or session.get("session_id") != session_id:
                return {"status":"STALE_SESSION"}
            if session.get("status") != "IN_PROGRESS":
                return {"status":"ALREADY_FINISHED"}
            answers = session.get("answers", [])
            if not isinstance(answers, list) or index != len(answers):
                return {"status":"OUT_OF_ORDER"}
            question = QUESTIONS[index]
            answers.append({"question":index+1,"choice":choice,
                "correct":choice==question["correct"],"critical":bool(question["critical"]),
                "answered_at":timestamp})
            session["answers"] = answers
            if len(answers) < len(QUESTIONS):
                return {"status":"NEXT","next_index":len(answers)}
            score = sum(1 for answer in answers if answer.get("correct") is True)
            critical_pass = all((not question["critical"]) or answers[i].get("correct") is True
                for i, question in enumerate(QUESTIONS))
            passed = score >= TRADER_PASS_SCORE and critical_pass
            session.update({"status":"PASSED" if passed else "FAILED","score":score,
                "critical_pass":critical_pass,"finished_at":timestamp})
            attempts = db.setdefault("trader_certification_attempts", [])
            if not isinstance(attempts, list):
                raise ValueError("TRADER_CERTIFICATION_ATTEMPTS_INVALID")
            attempts.append({"uid":uid,"session_id":session_id,"quiz_version":TRADER_QUIZ_VERSION,
                "score":score,"critical_pass":critical_pass,"passed":passed,"finished_at":timestamp})
            del attempts[:-1000]
            if passed:
                certifications = db.setdefault("trader_certifications", {})
                certifications[uid] = {"passed":True,"score":score,"critical_pass":True,
                    "quiz_version":TRADER_QUIZ_VERSION,"course_id":TRADER_COURSE_ID,
                    "passed_at":timestamp,"session_id":session_id}
                users = db.setdefault("users", {})
                user = users.get(uid)
                if not isinstance(user, dict):
                    raise ValueError("USER_NOT_FOUND")
                course_state = user.setdefault("academy", {}).setdefault("courses", {}).setdefault(
                    TRADER_COURSE_ID, {"stage":0,"completed":[]})
                completed = course_state.setdefault("completed", [])
                completed_ids = {int(value) for value in completed}
                if TRADER_CERTIFICATION_STAGE not in completed_ids:
                    completed.append(TRADER_CERTIFICATION_STAGE)
                course_state["stage"] = max(int(course_state.get("stage",0) or 0), TRADER_CERTIFICATION_STAGE)
                course_state["certification_passed_at"] = timestamp
            return {"status":"PASSED" if passed else "FAILED","score":score,"critical_pass":critical_pass}
        try:
            result = state_manager.atomic_update(record)
        except Exception:
            bot.answer_callback_query(call.id, "שמירת התשובה נכשלה. ההסמכה לא השתנתה.", show_alert=True)
            return
        if result.get("status") in {"STALE_SESSION","ALREADY_FINISHED","OUT_OF_ORDER"}:
            bot.answer_callback_query(call.id, "המבחן פג או שהתשובה כבר נרשמה. פתח /trader_test מחדש.", show_alert=True)
            return
        bot.answer_callback_query(call.id, "התשובה נשמרה")
        if result.get("status") == "NEXT":
            _send_question(bot, call.message.chat.id, uid, session_id,
                int(result["next_index"]), message_id=call.message.message_id)
            return
        if result.get("status") == "PASSED":
            final_text = (f"✅ עברת את מבחן הסמכת סוחר SLH: {result['score']}/10.\n"
                "ההסמכה נשמרה בצד השרת. אפשר לפתוח את /chart או את ה-Mini App.\n\n"
                "אין בכך אישור להפקדות BNB/TON, למשיכות או למסחר on-chain.")
        else:
            final_text = (f"📘 תוצאת מבחן: {result.get('score',0)}/10. לא הוענקה הרשאת מסחר.\n"
                "עברו שוב על החומר ונסו מחדש ב-/trader_test.")
        try:
            bot.edit_message_text(final_text, call.message.chat.id, call.message.message_id)
        except Exception:
            bot.send_message(call.message.chat.id, final_text)
