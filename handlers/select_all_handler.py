"""Copy-friendly public guide command.

Telegram bots cannot read chat history or select messages already on screen.
This command returns the public guide in a single copy-friendly reply.
"""
from core.command_catalog import render_public_help


def build_select_all_text():
    try:
        guide = render_public_help("Me_ad_main")
    except Exception:
        guide = "📘 מדריך SLH Spark לא זמין כרגע."
    return (
        "📋 SLH Spark — ריכוז תוכן להעתקה\n"
        "הבוט אינו יכול לקרוא את היסטוריית הצ׳אט או לסמן הודעות שכבר הוצגו. "
        "הפקודה מרכזת את מדריך הפקודות הציבורי בלבד.\n\n"
        + guide
    )


def register(bot):
    @bot.message_handler(commands=["select_all"])
    def select_all_cmd(msg):
        bot.reply_to(msg, build_select_all_text())
