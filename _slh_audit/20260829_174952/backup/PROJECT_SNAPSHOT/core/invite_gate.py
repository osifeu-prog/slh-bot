import os


def invite_gate_enabled():
    return os.getenv("ALPHA_INVITE_OPEN", "0") == "1"


def can_start_onboarding(*, is_owner, is_existing_user):
    if is_owner:
        return True

    if is_existing_user:
        return True

    return invite_gate_enabled()
