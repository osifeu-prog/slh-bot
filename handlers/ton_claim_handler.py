"""Legacy TON claim route.

The old /claim_ton implementation performed a money mutation and then wrote a
stale db.json snapshot. It is intentionally disabled until a user-binding
protocol is implemented for TON deposits.
"""


def register(bot):
    @bot.message_handler(commands=["claim_ton", "ton_claim"])
    def claim_ton_cmd(msg):
        bot.reply_to(
            msg,
            "⛔ TON claim legacy route is disabled.\n"
            "הפקדות TON עוברות במסלול המאומת /ton_check עם TX hash.\n"
            "חיבור/אימות ארנק TON מתבצע דרך Mini App + TON Connect."
        )

    print("⚠️ legacy ton_claim_handler loaded (claim disabled)")
