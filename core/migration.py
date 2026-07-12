from core import profile_manager


def migrate_user(uid):

    uid=str(uid)

    db=profile_manager.load_db()

    user=db.get(
        "users",
        {}
    ).get(
        uid
    )

    if not user:
        return False


    changed=False


    # old balance -> wallet
    if "balance" in user:

        user.setdefault(
            "wallet",
            {}
        )

        user["wallet"]["credits"] = user.pop(
            "balance"
        )

        changed=True


    # old points -> gamification

    if "points" in user:

        user.setdefault(
            "gamification",
            {}
        )

        user["gamification"]["points"] = user.pop(
            "points"
        )

        user["gamification"]["level"] = (
            user["gamification"]["points"]//100
        )+1

        changed=True


    if changed:

        profile_manager.save_db(db)


    return changed



def migrate_all():

    db=profile_manager.load_db()

    count=0

    for uid in list(
        db.get("users",{}).keys()
    ):

        if migrate_user(uid):
            count+=1


    return count
