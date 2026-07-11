_ADMIN_IDS = [8789977826, 224223270]

def is_admin(m):
    uid = m.from_user.id if hasattr(m, 'from_user') else m
    return uid in _ADMIN_IDS
