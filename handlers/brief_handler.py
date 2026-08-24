from core.morning_brief import get_morning_brief


def register(bot, context=None):
    @bot.message_handler(commands=["brief"])
    def brief_cmd(m):
        uid = str(m.from_user.id)
        brief = get_morning_brief(uid)
        bot.reply_to(m, brief, parse_mode=None)

    @bot.message_handler(commands=["valuation"])
    def valuation_cmd(m):
        from core.ton_lab import valuation_report
        bot.reply_to(m, valuation_report(), parse_mode=None)

    @bot.message_handler(commands=["onchain"])
    def onchain_cmd(m):
        from core.deposit_monitor import get_onchain_status
        import json
        status = get_onchain_status()
        text = json.dumps(status, ensure_ascii=False, indent=2)
        bot.reply_to(m, text, parse_mode=None)

    print("✅ brief_handler loaded")
