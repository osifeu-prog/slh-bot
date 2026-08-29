import datetime

from core import profile_manager
from core import academy_manager


COURSE_ID = "bitcoin_mastery"
REQUIRED_STAGE = 3


def register(bot):

    pending = {}

    @bot.message_handler(commands=["graduate"])
    def graduate_start(message):

        uid = str(message.from_user.id)

        progress = academy_manager.get_course(
            uid,
            COURSE_ID
        )

        stage = progress.get(
            "stage",
            0
        )

        if stage < REQUIRED_STAGE:
            bot.reply_to(
                message,
                f"🎓 בדיקת סיום קורס\n\n"
                f"עדיין לא הושלם הקורס.\n"
                f"התקדמות: {stage}/{REQUIRED_STAGE}"
            )
            return


        user = profile_manager.get_user(uid)

        if user.get("academy", {}).get("graduated"):
            bot.reply_to(
                message,
                "✅ אתה כבר בור האקדמיה"
            )
            return


        pending[uid] = True

        bot.reply_to(
            message,
            "🎓 ברכות! השלמת את הקורס.\n\n"
            "שלב הבא: העברת בעלות לבוט העצמאי שלך.\n"
            "שלח /confirm_graduation לאישור."
        )


    @bot.message_handler(commands=["confirm_graduation"])
    def graduate_confirm(message):

        uid = str(message.from_user.id)

        if uid not in pending:
            bot.reply_to(
                message,
                "אין תהליך סיום פעיל."
            )
            return


        pending.pop(uid, None)

        profile_manager.update_user(
            uid,
            {
                "academy":{
                    "graduated": True,
                    "graduation_date":
                        datetime.datetime.utcnow().isoformat(),
                    "instance_type":
                        "student"
                }
            }
        )

        bot.reply_to(
            message,
            "🎓 סיום קורס הושלם!\n\n"
            "אתה מודר כבור SLH Academy.\n"
            "שלב הבא יהיה חיבור הבוט העצמאי שלך."
        )


    print("✅ ownership_transfer_handler loaded")
