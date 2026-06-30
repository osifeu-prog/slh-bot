from core_engine import (
    get_or_create_user,
    set_progress,
    get_progress,
    next_stage
)

def patch_course_handlers(bot):

    @bot.message_handler(commands=['start_course'])
    def start_course(m):
        uid = m.from_user.id

        set_progress(uid, "bitcoin_mastery", {
            "current_stage": 0,
            "completed": []
        })

        bot.reply_to(m, "COURSE STARTED 🚀")

    @bot.message_handler(commands=['next'])
    def next_lesson(m):
        uid = m.from_user.id

        stage, status = next_stage(uid, "bitcoin_mastery")

        if status == "COURSE_COMPLETED":
            bot.reply_to(m, "🎉 COURSE COMPLETED")
            return

        if not stage:
            bot.reply_to(m, "ERROR: COURSE NOT FOUND")
            return

        text = stage.get("content", "NO CONTENT")
        bot.reply_to(m, f"📘 NEXT LESSON:\n{text}")

    @bot.message_handler(commands=['progress'])
    def progress(m):
        uid = m.from_user.id
        p = get_progress(uid, "bitcoin_mastery")
        bot.reply_to(m, f"PROGRESS:\n{p}")
