"""Telegram interface for the isolated paper AMM simulator."""
from telebot import types

from core import paper_exchange as paper


ERROR_TEXT = {
    "REQUEST_ID_REQUIRED": "הפעולה נחסמה: חסר מזהה בקשה בטוח.",
    "INVALID_SIDE": "סוג הפעולה אינו תקין. השתמשו בקנייה או במכירה.",
    "INVALID_AMOUNT": "הכמות חייבת להיות מספר חיובי.",
    "AMOUNT_OUT_OF_RANGE": "הכמות חייבת להיות בין 0.01 ל־100,000 יחידות דמו.",
    "INSUFFICIENT_DEMO_CREDITS": "אין מספיק Demo Credits בארנק הדמו. לא בוצע מסחר.",
    "INSUFFICIENT_DEMO_SLH": "אין מספיק Demo SLH בארנק הדמו. לא בוצע מסחר.",
    "AMOUNT_TOO_SMALL": "הכמות קטנה מדי לביצוע לאחר חישוב העמלה. לא בוצע מסחר.",
    "PAPER_SIM_STATE_INVALID": "סביבת הדמו זוהתה כלא תקינה ולכן נחסמה. לא שונו יתרות אמיתיות.",
    "PAPER_SIM_POOL_INVALID": "מאגר הדמו אינו תקין ולכן המסחר נחסם.",
    "PAPER_SIM_UID_INVALID": "לא ניתן לזהות את חשבון הדמו.",
    "PAPER_SIM_USER_STATE_INVALID": "חשבון הדמו אינו תקין. לא שונו יתרות אמיתיות.",
    "PAPER_SIM_BALANCE_INVALID": "יתרת הדמו אינה תקינה ולכן המסחר נחסם.",
}


def _menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👛 תיק הדמו", callback_data="paper:portfolio"),
        types.InlineKeyboardButton("📊 שער AMM", callback_data="paper:quote"),
    )
    markup.add(
        types.InlineKeyboardButton("🧾 היסטוריית דמו", callback_data="paper:history"),
        types.InlineKeyboardButton("🏆 לוח מובילים", callback_data="paper:leaderboard"),
    )
    return markup


def _portfolio_text(snapshot):
    change = float(snapshot["change_from_start_credits"])
    change_label = "+" if change > 0 else ""
    return (
        "👛 תיק המסחר המדומה שלך\n\n"
        f"💵 Demo Credits זמינים: {paper.compact(snapshot['demo_credits'])}\n"
        f"🪙 Demo SLH זמינים: {paper.compact(snapshot['demo_slh'])}\n"
        f"📈 שער AMM משוער: {paper.compact(snapshot['price_credits_per_slh'])} Demo Credits ל־Demo SLH\n"
        f"💼 שווי תיק משוער: {paper.compact(snapshot['portfolio_value_credits'])} Demo Credits\n"
        f"📊 שינוי משוער מהקצאת הפתיחה: {change_label}{paper.compact(snapshot['change_from_start_credits'])} Demo Credits\n\n"
        "הערכת השווי היא לפי שער ה־pool הנוכחי, לא לפי מחיר מובטח למכירה."
    )


def _quote_text(snapshot):
    return (
        "📊 שוק דמו: DEMO-SLH / DEMO-CREDITS\n\n"
        f"🏷️ שער pool נוכחי: {paper.compact(snapshot['price_credits_per_slh'])} Demo Credits ל־Demo SLH\n"
        f"💧 רזרבת pool: {paper.compact(snapshot['pool_slh'])} Demo SLH\n"
        f"💧 רזרבת pool: {paper.compact(snapshot['pool_credits'])} Demo Credits\n"
        "💸 עמלת סימולציה: 0.3% לכל עסקה\n"
        "🔄 מודל: Automated Market Maker (constant product); העסקאות משנות את השער ואת השפעת המחיר.\n\n"
        "אלה נתוני סימולציה פנימיים בלבד, לא נתוני שוק חיים."
    )


def _history_text(rows):
    if not rows:
        return "🧾 עדיין אין עסקאות דמו בחשבון שלך.\n\nנסה/י /sim_buy 100 או /sim_sell 10."
    lines = ["🧾 10 העסקאות האחרונות שלך בסימולציה", ""]
    for row in rows:
        side = "קנייה" if row.get("side") == "buy" else "מכירה"
        lines.append(
            f"{row.get('id')} · {side}\n"
            f"  כמות: {paper.compact(row.get('amount_slh', 0))} Demo SLH\n"
            f"  תמורה/עלות: {paper.compact(row.get('amount_credits', 0))} Demo Credits\n"
            f"  מחיר ממוצע: {paper.compact(row.get('average_price_credits_per_slh', 0))}\n"
            f"  עמלה: {paper.compact(row.get('fee_amount', 0))} {row.get('fee_asset', '')}\n"
            f"  השפעת מחיר: {paper.compact(row.get('price_impact_pct', 0))}%"
        )
    return "\n".join(lines)


def _leaderboard_text(rows):
    if not rows:
        return "🏆 לוח הדמו עדיין ריק. פתח/י סימולציה דרך /simulation."
    lines = ["🏆 לוח מובילי הדמו", "מדורג לפי שווי תיק מדומה בלבד — לא כסף או Credits אמיתיים.", ""]
    for idx, row in enumerate(rows, 1):
        delta = float(row.get("change_from_start_credits", 0))
        sign = "+" if delta > 0 else ""
        lines.append(
            f"{idx}. {row['alias']} · שווי {paper.compact(row['portfolio_value_credits'])} "
            f"· שינוי {sign}{paper.compact(delta)} Demo Credits"
        )
    return "\n".join(lines)


def _trade_text(result, side):
    if result.get("status") != "FILLED":
        return "⛔ " + ERROR_TEXT.get(result.get("error"), "העסקה המדומה נחסמה. לא שונו יתרות אמיתיות.")
    row = result["trade"]
    duplicate_note = "\nℹ️ זוהתה בקשה חוזרת; העסקה לא בוצעה שוב." if result.get("duplicate") else ""
    if side == "buy":
        action = (
            f"✅ קנייה מדומה הושלמה\n"
            f"💵 תקציב כולל: {paper.compact(row['amount_credits'])} Demo Credits\n"
            f"🪙 התקבל: {paper.compact(row['amount_slh'])} Demo SLH\n"
            f"💸 עמלה: {paper.compact(row['fee_amount'])} Demo Credits"
        )
    else:
        action = (
            f"✅ מכירה מדומה הושלמה\n"
            f"🪙 נמכר: {paper.compact(row['amount_slh'])} Demo SLH\n"
            f"💵 התקבל: {paper.compact(row['amount_credits'])} Demo Credits\n"
            f"💸 עמלה: {paper.compact(row['fee_amount'])} Demo SLH"
        )
    snapshot = result["account"]
    return (
        action
        + f"\n📊 מחיר ביצוע ממוצע: {paper.compact(row['average_price_credits_per_slh'])} Demo Credits ל־Demo SLH"
        + f"\n📉 השפעת מחיר משוערת: {paper.compact(row['price_impact_pct'])}%"
        + f"\n🏷️ שער pool אחרי העסקה: {paper.compact(row['price_after'])}"
        + "\n\n👛 יתרות הדמו לאחר העסקה:"
        + f"\n• Demo Credits: {paper.compact(snapshot['demo_credits'])}"
        + f"\n• Demo SLH: {paper.compact(snapshot['demo_slh'])}"
        + duplicate_note
    )


def register(bot):
    @bot.message_handler(commands=["simulation", "sim"])
    def simulation(message):
        try:
            uid = str(message.from_user.id)
            snapshot = paper.account(uid)
            text = (
                "🧪 SLH Spark · Paper Exchange\n\n"
                "ברוך הבא למסלול מסחר דמו מבודד. כל היתרות הן Demo Credits ו־Demo SLH מדומים בלבד.\n\n"
                "🎁 הקצאת פתיחה חד־פעמית: 1,000 Demo Credits + 1,000 Demo SLH.\n"
                "💱 /sim_buy 100 — קנייה עם תקציב של 100 Demo Credits\n"
                "💱 /sim_sell 10 — מכירת 10 Demo SLH\n"
                "👛 /sim_portfolio — תיק ויתרות\n"
                "📊 /sim_quote — שער ה־pool והנזילות\n"
                "🧾 /sim_history — היסטוריית העסקאות\n"
                "🏆 /sim_leaderboard — לוח מובילים\n\n"
                "💸 עמלה מדומה: 0.3%. המחיר משתנה בעקבות העסקאות לפי מודל AMM, ועסקה גדולה יכולה ליצור השפעת מחיר.\n\n"
                "🛡️ אין שימוש ב־Credits האמיתיים, ב־ledger האמיתי, בפקודות הבורסה החיה, בארנק on-chain, בחתימות או בהפקדות. שערי Production אינם משתנים.\n\n"
                "הסימולטור משתמש במחיר pool מדומה — לא במחיר שוק חי ולא בהבטחת רווח."
            )
            bot.send_message(message.chat.id, text, reply_markup=_menu())
        except Exception as exc:
            print("[PAPER_SIM] open:", type(exc).__name__)
            bot.reply_to(message, "לא ניתן לפתוח כרגע את סביבת הדמו. יתרות Production לא שונו.")

    @bot.message_handler(commands=["sim_portfolio"])
    def portfolio(message):
        try:
            bot.reply_to(message, _portfolio_text(paper.account(str(message.from_user.id))))
        except Exception as exc:
            print("[PAPER_SIM] portfolio:", type(exc).__name__)
            bot.reply_to(message, "לא ניתן לקרוא את תיק הדמו כרגע. יתרות Production לא שונו.")

    @bot.message_handler(commands=["sim_quote"])
    def quote(message):
        try:
            bot.reply_to(message, _quote_text(paper.account(str(message.from_user.id))))
        except Exception as exc:
            print("[PAPER_SIM] quote:", type(exc).__name__)
            bot.reply_to(message, "נתוני שוק הדמו אינם זמינים כרגע.")

    @bot.message_handler(commands=["sim_buy", "sim_sell"])
    def execute_trade(message):
        parts = (message.text or "").split()
        uid = str(message.from_user.id)
        side = "buy" if (parts[0].split("@", 1)[0] == "/sim_buy") else "sell"
        if len(parts) != 2:
            usage = "/sim_buy <demo_credits_budget>" if side == "buy" else "/sim_sell <demo_slh_quantity>"
            bot.reply_to(message, f"שימוש: {usage}\n\nפתח/י /simulation להסבר מלא.")
            return
        request_id = f"telegram:{message.chat.id}:{message.message_id}"
        try:
            result = paper.trade(uid, side, parts[1], request_id)
            bot.reply_to(message, _trade_text(result, side))
        except Exception as exc:
            print("[PAPER_SIM] trade:", type(exc).__name__)
            bot.reply_to(message, "המסחר המדומה נחסם בגלל בדיקת תקינות. לא בוצע שינוי ביתרות האמיתיות.")

    @bot.message_handler(commands=["sim_history"])
    def history(message):
        try:
            bot.reply_to(message, _history_text(paper.history(str(message.from_user.id))))
        except Exception as exc:
            print("[PAPER_SIM] history:", type(exc).__name__)
            bot.reply_to(message, "לא ניתן לקרוא את היסטוריית הדמו כרגע.")

    @bot.message_handler(commands=["sim_leaderboard"])
    def leaderboard(message):
        try:
            bot.reply_to(message, _leaderboard_text(paper.leaderboard()))
        except Exception as exc:
            print("[PAPER_SIM] leaderboard:", type(exc).__name__)
            bot.reply_to(message, "לוח מובילי הדמו אינו זמין כרגע.")

    @bot.callback_query_handler(func=lambda call: isinstance(getattr(call, "data", None), str) and call.data.startswith("paper:"))
    def simulation_button(call):
        try:
            action = call.data.split(":", 1)[1]
            uid = str(call.from_user.id)
            if action in {"portfolio", "quote"}:
                snapshot = paper.account(uid)
                text = _portfolio_text(snapshot) if action == "portfolio" else _quote_text(snapshot)
            elif action == "history":
                text = _history_text(paper.history(uid))
            elif action == "leaderboard":
                text = _leaderboard_text(paper.leaderboard())
            else:
                text = "פעולה לא מוכרת."
            try:
                bot.answer_callback_query(call.id)
            except Exception:
                pass
            bot.send_message(call.message.chat.id, text, reply_markup=_menu())
        except Exception as exc:
            print("[PAPER_SIM] callback:", type(exc).__name__)
            try:
                bot.answer_callback_query(call.id, "לא ניתן לפתוח את מסך הדמו.")
            except Exception:
                pass
