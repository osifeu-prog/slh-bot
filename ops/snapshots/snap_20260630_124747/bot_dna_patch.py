from dna_lock import acquire_lock, release_lock
from safe_progress import enroll_user, get_progress

def patch(bot):

    @bot.message_handler(commands=['start_course'])
    def start_course(m):
        uid = m.from_user.id

        if not acquire_lock(uid):
            bot.reply_to(m, "⚠️ כבר בתהליך / או כבר נרשמת")
            return

        try:
            ok = enroll_user(uid, "bitcoin_mastery")

            if not ok:
                bot.reply_to(m, "⚠️ כבר רשום לקורס")
            else:
                bot.reply_to(m, "✅ נרשמת בהצלחה לקורס")

        finally:
            release_lock(uid)


    @bot.message_handler(commands=['progress'])
    def progress(m):
        uid = m.from_user.id
        p = get_progress(uid)
        bot.reply_to(m, f"📊 PROGRESS:\n{p}")
