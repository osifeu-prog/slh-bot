"""SLH Personal AI Identity Layer"""

OWNER_ID = "972500000001"

DEFAULT_ASSISTANT_NAME = "SLH OS Assistant"
OWNER_ASSISTANT_NAME = "רובוטוש"


def get_assistant_name(user_id=None):
    if str(user_id) == OWNER_ID:
        return OWNER_ASSISTANT_NAME

    return DEFAULT_ASSISTANT_NAME
