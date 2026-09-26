from core.trust_router import guard


def main():
    ok = guard("Explain how BNB gas works", "test-user")
    assert ok is True

    blocked = guard(
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456",
        "test-user-2",
    )
    assert isinstance(blocked, tuple)
    assert blocked[0] is False

    print("TRUST_ROUTER_TESTS: PASS")


if __name__ == "__main__":
    main()
