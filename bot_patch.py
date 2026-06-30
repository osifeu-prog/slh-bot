from core_engine import get_or_create_user, set_progress, get_progress

def patch_start_handler(bot):

    @bot.message_handler(commands=['start'])
    def start(m):
        user = get_or_create_user(
            m.from_user.id,
            m.from_user.first_name or "user"
        )
        bot.reply_to(m, f"Welcome {user['name']} | ID: {m.from_user.id}")


def patch_course_handler(bot):

    @bot.message_handler(commands=['start_course'])
    def start_course(m):
        uid = m.from_user.id

        set_progress(uid, "bitcoin_mastery", {
            "current_stage": 1,
            "completed": [],
            "updated": True
        })

        bot.reply_to(m, "COURSE STARTED")


def patch_progress_handler(bot):

    @bot.message_handler(commands=['progress'])
    def progress(m):
        uid = m.from_user.id

        p = get_progress(uid)

        bot.reply_to(m, f"PROGRESS:\n{p}")
