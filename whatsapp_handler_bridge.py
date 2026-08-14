"""
SLH WhatsApp Store Bridge

CLI contract:
    python3 whatsapp_handler_bridge.py <uid> shop
    python3 whatsapp_handler_bridge.py <uid> 'buy <item_id>'

This file is an adapter only.
Economy and store logic remain in their existing modules.
"""

import sys

from store.engine import format_shop_message, buy_item
from core.economy_bridge import get_balance, spend


def usage():
    print(
        "Usage:\n"
        "  python3 whatsapp_handler_bridge.py <uid> shop\n"
        "  python3 whatsapp_handler_bridge.py <uid> 'buy <item_id>'",
        file=sys.stderr,
    )


def main():
    if len(sys.argv) < 3:
        print("ERROR: missing UID or command", file=sys.stderr)
        usage()
        return 2

    uid = sys.argv[1].strip()
    cmd = sys.argv[2].strip()

    if not uid:
        print("ERROR: empty UID", file=sys.stderr)
        return 2

    if not cmd:
        print("ERROR: empty command", file=sys.stderr)
        usage()
        return 2

    if cmd == "shop":
        print(format_shop_message(get_balance(uid)))
        return 0

    if cmd == "buy":
        print("ERROR: missing item_id", file=sys.stderr)
        usage()
        return 2

    if cmd.startswith("buy "):
        parts = cmd.split()

        if len(parts) != 2:
            print("ERROR: invalid buy syntax", file=sys.stderr)
            usage()
            return 2

        item_id = parts[1]

        ok, text = buy_item(
            uid,
            item_id,
            get_balance,
            spend,
        )

        print(text)
        return 0 if ok else 1

    print(f"ERROR: unknown command: {cmd}", file=sys.stderr)
    usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
