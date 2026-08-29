from core.message_utils import safe_clip

from plugins.leaderboard import LeaderboardPlugin



def show_leaderboard(db_path="state/db.json"):

    lb = LeaderboardPlugin(db_path)

    top = lb.get_top(10)

    text = "🏆 טבלת המובילים 🏆\n\n"

    for i, (uid, data) in enumerate(top, 1):

        name = data.get("name", f"User{uid}")

        credits = data.get("wallet", {}).get("credits", 0)

        text += f"{i}. {name} - {credits} SLH\n"

    return text





def register(bot):



    @bot.message_handler(commands=['top'])

    def top_handler(m):

        bot.reply_to(

            m,

            safe_clip(show_leaderboard())

        )



