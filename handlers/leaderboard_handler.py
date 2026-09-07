from core.message_utils import safe_clip

from plugins.leaderboard import LeaderboardPlugin



def show_leaderboard(db_path="state/db.json"):

    lb = LeaderboardPlugin(db_path)

    top = lb.get_top(10)

    text = "🏆 טבלת המובילים 🏆\n\n"

    for i, (uid, data) in enumerate(top, 1):

        name = data.get("name", f"User{uid}")

        points = (data.get("gamification") or {}).get("points", 0)

        text += f"{i}. {name} - {points} נקודות\n"

    return text





def register(bot):



    @bot.message_handler(commands=['top','leaderboard','points'])

    def top_handler(m):

        bot.reply_to(

            m,

            safe_clip(show_leaderboard())

        )



