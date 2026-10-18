"""Read-only Telegram pitch mode for SLH Spark.

This module only renders presentation text and synthetic examples. It does not
read or mutate financial ledgers, balances, wallets, payment or exchange gates.
"""

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


PITCH_SLIDES = (
    {
        "title": "SLH Spark — אקוסיסטם דיגיטלי",
        "body": (
            "SLH Spark מחברת בין אקדמיה דיגיטלית, טוקן SLH, סוכני AI "
            "ואוטומציה בתוך מערכת SLH OS.\n\n"
            "הגישה העסקית: לפתח מוצרים שימושיים, הכנסות מדידות ושותפויות "
            "תוך שיפור השקיפות והבקרה התפעולית."
        ),
    },
    {
        "title": "Academy — למידה ותוכן בתשלום",
        "body": (
            "במערכת קיימים מסלולי לימוד חינמיים ובתשלום, קטלוג קורסים, "
            "גישה לשיעורים ומעקב התקדמות.\n\n"
            "הזדמנויות לצמיחה: הפצת תוכן, שותפי הוראה, חבילות לארגונים "
            "ושירותי למידה דיגיטלית.\n\n"
            "נתוני מכירות, המרות ושימור יוצגו כנתונים עסקיים רק לאחר אימות."
        ),
    },
    {
        "title": "Tokenomics — שימושים, הקצאות ורזרבות",
        "body": (
            "המודל הכלכלי של SLH מתאר את תפקיד הטוקן, שימושיו, מבנה ההקצאות "
            "ומנגנוני הרזרבה כפי שהוגדרו במסמכי המיזם.\n\n"
            "בפגישה נציג את הטוקונומיקה ממסמכי המקור. נתוני המודל והיתרות "
            "בפועל הם שתי שכבות נפרדות, והתאמה חשבונאית מדווחת לפי ראיות."
        ),
    },
    {
        "title": "SLH OS — AI ואוטומציה",
        "body": (
            "הבוט מרכז יכולות דיגיטליות כגון קורסים, סוכני AI, משימות "
            "ותהליכי עבודה.\n\n"
            "הדגמה טובה מתמקדת בזרימת משתמש אחת שעובדת מקצה לקצה, "
            "ומבדילה בין יכולת זמינה, יכולת בבדיקה ותוכנית להמשך."
        ),
    },
    {
        "title": "Financial Controls — סימולציה והתאמה",
        "body": (
            "מסלול הבקרה שאנו רוצים להדגים: כוונת פעולה → הצעת מחיר → "
            "ביצוע מדומה → מזהה אירוע → אישור → ledger → התאמת יתרה.\n\n"
            "ההדגמה המצורפת משתמשת בנתונים סינתטיים בלבד ואינה נוגעת "
            "ביתרות משתמשים או במסלולי כסף אמיתי."
        ),
    },
    {
        "title": "Partnership — הצעד הבא",
        "body": (
            "אנחנו מחפשים שותפויות ממוקדות בשלושה תחומים:\n"
            "• הפצת קורסים ותוכן דיגיטלי\n"
            "• מוצרי AI ואוטומציה\n"
            "• תשתיות Sandbox ותהליכי התאמה חשבונאית\n\n"
            "הצעד הבא המועדף: להגדיר פיילוט תחום, מדד הצלחה, אחראי ותאריך "
            "בדיקה. שערי ההפקדה, המסחר והמשיכה בכסף אמיתי נשארים סגורים."
        ),
    },
)


SIMULATION_DEMO = (
    "🧪 הדגמת סימולציה — נתונים סינתטיים בלבד\n\n"
    "תרחיש: SIM-DEMO-001\n"
    "פעולה: רכישה מדומה בשווי 100 יחידות וירטואליות\n\n"
    "1. Intent: נוצרה כוונת פעולה מדומה\n"
    "2. Quote: הצעת מחיר לדוגמה — 100 יחידות\n"
    "3. Execution: בוצעה סימולציה בלבד\n"
    "4. Event ID: SIM-TX-0001\n"
    "5. Confirmation: MOCK_CONFIRMED\n"
    "6. Ledger: נרשמה תנועת דוגמה בסביבה המדומה\n"
    "7. Expected balance: 900 יחידות וירטואליות\n"
    "8. Observed balance: 900 יחידות וירטואליות\n"
    "9. Variance: 0.00\n\n"
    "תוצאה בדוגמה: PASS\n\n"
    "⚠️ כל הערכים כאן סינתטיים לצורך הצגת הממשק בלבד. זו אינה רשומת "
    "ייצור, אינה עסקה אמיתית ואינה ראיה לכך שהתאמות הייצור הושלמו."
)


def render_slide(index):
    """Render one public slide without querying financial or personal data."""
    if not isinstance(index, int) or isinstance(index, bool):
        index = 0
    index = max(0, min(index, len(PITCH_SLIDES) - 1))
    slide = PITCH_SLIDES[index]
    return (
        f"🚀 SLH SPARK | PITCH MODE\n\n"
        f"{slide['title']}\n\n"
        f"{slide['body']}\n\n"
        f"מסך {index + 1}/{len(PITCH_SLIDES)}"
    )


def render_simulation_demo():
    return SIMULATION_DEMO


def build_slide_keyboard(index):
    """Build a bounded, stateless inline keyboard for a slide."""
    index = max(0, min(int(index), len(PITCH_SLIDES) - 1))
    markup = InlineKeyboardMarkup(row_width=2)
    navigation = []

    if index > 0:
        navigation.append(
            InlineKeyboardButton(
                "◀️ הקודם",
                callback_data=f"slh_pitch:slide:{index - 1}",
            )
        )
    if index < len(PITCH_SLIDES) - 1:
        navigation.append(
            InlineKeyboardButton(
                "הבא ▶️",
                callback_data=f"slh_pitch:slide:{index + 1}",
            )
        )
    else:
        navigation.append(
            InlineKeyboardButton(
                "🔄 התחלה מחדש",
                callback_data="slh_pitch:slide:0",
            )
        )

    if navigation:
        markup.row(*navigation)

    if index == 4:
        markup.row(
            InlineKeyboardButton(
                "🧪 הצג דוגמת סימולציה",
                callback_data="slh_pitch:sim",
            )
        )

    if index == len(PITCH_SLIDES) - 1:
        markup.row(
            InlineKeyboardButton(
                "🎓 פתח את Academy",
                callback_data="slh_pitch:academy",
            )
        )
        markup.row(
            InlineKeyboardButton(
                "סיום המצגת",
                callback_data="slh_pitch:close",
            )
        )

    return markup


def _simulation_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "↩️ חזרה למצגת",
            callback_data="slh_pitch:slide:4",
        )
    )
    return markup


def _closed_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "🔄 הצג את המצגת שוב",
            callback_data="slh_pitch:slide:0",
        )
    )
    return markup


def register(bot):
    @bot.message_handler(commands=["pitch"])
    def pitch_command(message):
        bot.send_message(
            message.chat.id,
            render_slide(0),
            reply_markup=build_slide_keyboard(0),
            parse_mode=None,
            disable_web_page_preview=True,
        )

    @bot.callback_query_handler(
        func=lambda call: bool(call.data)
        and call.data.startswith("slh_pitch:")
    )
    def pitch_callback(call):
        data = call.data or ""
        message = getattr(call, "message", None)
        if message is None:
            bot.answer_callback_query(
                call.id,
                "פתח את המצגת מתוך השיחה עם הבוט.",
                show_alert=False,
            )
            return

        chat_id = message.chat.id
        message_id = message.message_id

        if data == "slh_pitch:sim":
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                render_simulation_demo(),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=_simulation_keyboard(),
                parse_mode=None,
                disable_web_page_preview=True,
            )
            return

        if data == "slh_pitch:academy":
            bot.answer_callback_query(call.id)
            try:
                from handlers.academy_menu_handler import _send_academy

                _send_academy(bot, chat_id, str(call.from_user.id))
            except Exception as exc:
                print("[PITCH] Academy launch failed:", type(exc).__name__)
                bot.send_message(
                    chat_id,
                    "לא הצלחתי לפתוח את Academy כרגע. נסה /academy.",
                )
            return

        if data == "slh_pitch:close":
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "תודה שבחנת את SLH Spark.\n\n"
                "אפשר לפתוח את המצגת שוב בכל עת באמצעות /pitch.",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=_closed_keyboard(),
                parse_mode=None,
                disable_web_page_preview=True,
            )
            return

        if data.startswith("slh_pitch:slide:"):
            try:
                index = int(data.rsplit(":", 1)[1])
            except (TypeError, ValueError):
                bot.answer_callback_query(call.id, "מסך לא תקין")
                return

            if index < 0 or index >= len(PITCH_SLIDES):
                bot.answer_callback_query(call.id, "מסך לא תקין")
                return

            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                render_slide(index),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=build_slide_keyboard(index),
                parse_mode=None,
                disable_web_page_preview=True,
            )
            return

        bot.answer_callback_query(call.id, "פעולה לא מוכרת")
