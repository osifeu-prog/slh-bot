from core.action_trust import evaluate, is_sensitive


def main():
    assert is_sensitive("wallet_send")
    assert evaluate(
        action="wallet_send",
        authenticated=False,
        authorized=False,
        user_confirmed=False,
        trust_level="low",
        money_involved=True,
    )["decision"] == "BLOCK"

    assert evaluate(
        action="wallet_send",
        authenticated=True,
        authorized=True,
        user_confirmed=False,
        trust_level="low",
        money_involved=True,
    )["decision"] == "REVIEW"

    assert evaluate(
        action="wallet_send",
        authenticated=True,
        authorized=True,
        user_confirmed=True,
        trust_level="low",
        money_involved=True,
    )["decision"] == "ALLOW"

    assert evaluate(
        action="external_tool",
        authenticated=True,
        authorized=True,
        user_confirmed=True,
        trust_level="high",
    )["decision"] == "BLOCK"

    print("ACTION_TRUST_TESTS: PASS")


if __name__ == "__main__":
    main()
