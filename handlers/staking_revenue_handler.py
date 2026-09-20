"""Guard the unfinished Revenue Share staking surface.

Revenue Share staking is not part of the canonical active staking authority yet.
The historical handler called APIs that do not exist in
core.staking_revenue_share. Keep the commands explicit and read-only until a
canonical implementation is connected to the active staking position model.
"""


INFO = (
    "⚠️ Revenue Share staking עדיין לא פעיל במסלול הקנוני.\n\n"
    "הסטייקינג הפעיל משתמש ב-Credits דרך /stake או /stake_lock.\n"
    "אין כאן חיוב, נעילה, חלוקה או משיכה של נכס."
)


def register(bot, context=None):
    @bot.message_handler(commands=["stake_revenue", "claim_revenue", "my_stake"])
    def revenue_staking_notice(m):
        bot.reply_to(m, INFO)

    print("staking_revenue_handler loaded (read-only guard)")
