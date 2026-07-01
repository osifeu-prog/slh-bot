def init(bot):
    @bot.message_handler(commands=['help'])
    def help_cmd(m):
        msg = (
            "📋 **פקודות זמינות:**\n"
            "🔹 /start – התחלה\n"
            "🔹 /join – הרשמה\n"
            "🔹 /myprogress – ההתקדמות שלי\n"
            "🔹 /leaderboard – טבלת מובילים\n"
            "🔹 /referral – קישור להזמנת חברים\n"
            "🔹 /courses – צפייה בקורס\n"
            "🔹 /start_course /next /progress – לימוד הקורס\n"
            "🔹 /project create/list/status – ניהול פרויקטים\n"
            "🔹 /agent_create /sendagent /inbox – סוכנים\n"
            "🔹 /ask – שאלה ל־AI (באמצעות /sendagent)\n"
            "🔹 /monitor – לוח מערכת (admin)\n"
            "🔹 /self_test – בדיקת תקינות (admin)\n"
            "🔹 /admins /add_admin /remove_admin – ניהול הרשאות\n"
            "🔹 /backup /rollback – גיבוי ושחזור\n"
            "🔹 /broadcast – הודעה לכולם (admin)"
        )
        bot.reply_to(m, msg, parse_mode="Markdown")
