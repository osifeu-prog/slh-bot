"""Pure in-memory 60-second Credits arcade session engine.

Entry is charged through the existing economy bridge. Rewards are points only;
no new Credits are minted by the game. Active sessions are intentionally kept
in memory, while the existing points leaderboard remains persistent.
"""
import random
import time

from core.economy_bridge import add_points, spend_credits

ENTRY_COST = 5
GAME_SECONDS = 60
ACTIVE = {}


def new_question(rng=random):
    a = rng.randint(2, 20)
    b = rng.randint(2, 20)
    op = rng.choice(["+", "-"])
    answer = a + b if op == "+" else a - b
    return f"{a} {op} {b} = ?", answer


def start_game(uid, now=None):
    uid = str(uid)
    if uid in ACTIVE:
        return {"status": "already_active", **ACTIVE[uid]}

    now = time.time() if now is None else now
    result = spend_credits(
        uid,
        ENTRY_COST,
        reason="arcade:entry",
        meta={"game": "math_60s"},
    )
    if result is False:
        return {"status": "insufficient_credits"}

    question, answer = new_question()
    ACTIVE[uid] = {
        "started": now,
        "deadline": now + GAME_SECONDS,
        "score": 0,
        "answer": answer,
        "questions": 1,
    }
    return {
        "status": "started",
        "question": question,
        "deadline": ACTIVE[uid]["deadline"],
    }


def answer_game(uid, answer, now=None):
    uid = str(uid)
    game = ACTIVE.get(uid)
    if not game:
        return {"status": "no_game"}

    now = time.time() if now is None else now
    if now >= game["deadline"]:
        return finish_game(uid)

    try:
        correct = int(str(answer).strip()) == int(game["answer"])
    except ValueError:
        correct = False

    if correct:
        game["score"] += 1

    question, next_answer = new_question()
    game["answer"] = next_answer
    game["questions"] += 1
    return {
        "status": "answered",
        "correct": correct,
        "score": game["score"],
        "question": question,
    }


def finish_game(uid):
    uid = str(uid)
    game = ACTIVE.pop(uid, None)
    if not game:
        return {"status": "already_finished"}

    points = game["score"] * 10
    if points:
        add_points(uid, points)

    return {
        "status": "finished",
        "score": game["score"],
        "points": points,
    }
