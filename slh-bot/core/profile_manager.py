import json
import os
from datetime import datetime


DB_PATH = "state/db.json"


def load_db():
    if not os.path.exists(DB_PATH):
        return {
            "users": {},
            "students": {},
            "tasks": {},
            "votes": {}
        }

    with open(DB_PATH,"r",encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    os.makedirs("state",exist_ok=True)

    with open(DB_PATH,"w",encoding="utf-8") as f:
        json.dump(
            db,
            f,
            indent=2,
            ensure_ascii=False
        )


def deep_merge(target, source):

    for k,v in source.items():

        if (
            isinstance(v,dict)
            and isinstance(target.get(k),dict)
        ):
            deep_merge(
                target[k],
                v
            )

        else:
            target[k]=v

    return target



def get_user(uid):

    uid=str(uid)

    db=load_db()

    users=db.setdefault("users",{})

    if uid not in users:

        users[uid]={
            "profile":{
                "created":datetime.utcnow().isoformat()
            },
            "wallet":{
                "credits":0
            },
            "academy":{
                "courses":{}
            },
            "gamification":{
                "points":0,
                "level":1
            },
            "referral":{
                "code":None,
                "count":0,
                "commission":0
            }
        }

        save_db(db)

    return users[uid]



def update_user(uid,data):

    uid=str(uid)

    db=load_db()

    user=db.setdefault(
        "users",
        {}
    ).setdefault(
        uid,
        {}
    )

    deep_merge(
        user,
        data
    )

    save_db(db)

    return user



def get_balance(uid):

    user=get_user(uid)

    return user.get(
        "wallet",
        {}
    ).get(
        "credits",
        0
    )



def add_balance(uid,amount):

    uid=str(uid)

    db=load_db()

    user=db.setdefault(
        "users",
        {}
    ).setdefault(
        uid,
        {}
    )

    wallet=user.setdefault(
        "wallet",
        {}
    )

    wallet["credits"]=wallet.get(
        "credits",
        0
    )+amount

    save_db(db)

    return wallet["credits"]



def add_points(uid,points):

    uid=str(uid)

    db=load_db()

    user=db.setdefault(
        "users",
        {}
    ).setdefault(
        uid,
        {}
    )

    game=user.setdefault(
        "gamification",
        {}
    )

    game["points"]=game.get(
        "points",
        0
    )+points

    game["level"]=(
        game["points"]//100
    )+1

    save_db(db)

    return game



def complete_course_stage(uid,course,stage):

    uid=str(uid)

    user=get_user(uid)

    courses=user.setdefault(
        "academy",
        {}
    ).setdefault(
        "courses",
        {}
    )

    c=courses.setdefault(
        course,
        {
            "stage":0,
            "completed":[]
        }
    )

    if stage not in c["completed"]:
        c["completed"].append(stage)

    c["stage"]=max(
        c["stage"],
        stage
    )

    update_user(
        uid,
        {
            "academy":{
                "courses":courses
            }
        }
    )

    return c



def get_progress(uid):

    return get_user(uid).get(
        "academy",
        {}
    )
