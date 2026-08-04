import json
import os


class LeaderboardPlugin:

    def __init__(self, db_path="state/db.json"):
        self.db_path = db_path


    def get_top(self, limit=10):
        if not os.path.exists(self.db_path):
            return []

        with open(self.db_path, encoding="utf-8") as f:
            db = json.load(f)

        users = db.get("users", {})

        ranked = sorted(
            users.items(),
            key=lambda x: x[1].get("credits", 0),
            reverse=True
        )

        return ranked[:limit]


def handle(text, chat_id, user_id, send):
    return None
