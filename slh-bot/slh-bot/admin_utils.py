from core.identity import OWNER_TELEGRAM_ID

_ADMIN_IDS = [OWNER_TELEGRAM_ID]

def is_admin(m):
    uid = m.from_user.id if hasattr(m, 'from_user') else m
    return int(uid) == OWNER_TELEGRAM_ID

def get_owner():
    return OWNER_TELEGRAM_ID
