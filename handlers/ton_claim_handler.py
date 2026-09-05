"""Legacy TON claim route.

The old /claim_ton implementation performed a money mutation and then wrote a
stale db.json snapshot. It is intentionally disabled until a user-binding
protocol is implemented for TON deposits.
"""


def register(bot):
    @bot.message_handler(commands=["claim_ton"])
    def claim_ton_cmd(msg):
        bot.reply_to(
            msg,
            "⛔ /claim_ton מושבת זמנית.\n"
            "הפקדות TON חייבות לעבור במסלול המאומת /ton_check עם TX hash.\n"
            "זיהוי בעלות על הפקדת TON עדיין דורש מנגנון binding ייעודי."
        )

    print("⚠️ legacy ton_claim_handler loaded (claim disabled)")
