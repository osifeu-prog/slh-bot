from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "state" / "db.json"


class TONWallet:
    """
    TON wallet adapter.

    This class intentionally does NOT perform blockchain transactions.
    It stores/reads the user's configured TON wallet address and leaves
    blockchain operations for a future verified TON provider integration.
    """

    def __init__(self, uid):
        self.uid = str(uid)

    def get_wallet(self):
        if not DB_PATH.exists():
            return None

        import json

        with DB_PATH.open("r", encoding="utf-8") as f:
            db = json.load(f)

        user = db.get("users", {}).get(self.uid, {})

        return user.get("ton_wallet")

    def set_wallet(self, address):
        if not DB_PATH.exists():
            raise FileNotFoundError(str(DB_PATH))

        import json

        with DB_PATH.open("r", encoding="utf-8") as f:
            db = json.load(f)

        users = db.setdefault("users", {})
        user = users.setdefault(self.uid, {})

        user["ton_wallet"] = str(address)

        with DB_PATH.open("w", encoding="utf-8") as f:
            json.dump(
                db,
                f,
                ensure_ascii=False,
                indent=2
            )

        return str(address)
