import json

ACTIONS_FILE = "state/reputation_actions.json"


def load_actions():
    with open(ACTIONS_FILE) as f:
        return json.load(f)


def verify_action(action, evidence=None):

    actions = load_actions()

    if action not in actions:
        return False, "Unknown action"

    rule = actions[action]

    if not rule.get("verified"):
        return False, "Action not verified"

    if evidence is None:
        return False, "Missing evidence"

    return True, "Verified"
