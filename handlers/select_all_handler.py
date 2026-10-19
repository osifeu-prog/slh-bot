"""Copy-friendly public guide command.

Telegram bots cannot select existing messages in the user's chat history.
Both /select all and /select_all return the public command guide in one reply.
"""
from core.command_catalog import render_public_help


def build_select_all_text():
    try:
        guide = render_public_help("Me_ad_main")
    except Exception:
        guide = "📘 מדריך SLH Spark לא זמין כרגע."
    return (
        "📋 SLH Spark — ריכוז תוכן להעתקה\n"
        "הפקודות ‎/select all ו־‎/select_all מרכזות את מדריך הפקודות הציבורי. "
        "הבוט אינו יכול לסמן או לבחור הודעות שכבר הוצגו בהיסטוריית הצ׳אט.\n\n"
        + guide
    )


def _command_and_args(msg):
    raw = str(getattr(msg, "text", "") or "").strip()
    parts = raw.split(maxsplit=1)
    if not parts:
        return "", ""
    command = parts[0].split("@", 1)[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    return command, args


def register(bot):
    @bot.message_handler(commands=["select_all", "select"])
    def select_all_cmd(msg):
        command, args = _command_and_args(msg)
        if command == "/select" and args.casefold() not in {"all", "כל"}:
            bot.reply_to(
                msg,
                "📌 שימוש: ‎/select all או ‎/select_all\n"
                "הפקודה מחזירה מדריך פקודות להעתקה; היא לא בוחרת הודעות בהיסטוריית Telegram.",
            )
            return
        bot.reply_to(msg, build_select_all_text())
