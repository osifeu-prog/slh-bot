import json, os

class VotingPlugin:
    def __init__(self, db_path="state/db.json"):
        self.db_path = db_path

    def _load(self):
        if not os.path.exists(self.db_path): return {}
        return json.load(open(self.db_path))

    def _save(self, db):
        json.dump(db, open(self.db_path, "w"), ensure_ascii=False, indent=2)

    def list_votes(self):
        db = self._load()
        return db.get("votes", [])

    def add_vote(self, vote_id, title, options):
        db = self._load()
        if "votes" not in db: db["votes"] = []
        db["votes"].append({"id": vote_id, "title": title, "options": options, "voters": {}})
        self._save(db)
