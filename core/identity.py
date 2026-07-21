"""SLH Personal AI Identity Layer"""

DEFAULT_ASSISTANT_NAME = "רובוטוש"

def get_assistant_name(user_id: str = None) -> str:
    # TODO: load from db.json per user
    return DEFAULT_ASSISTANT_NAME
