def register(bot):
    @bot.message_handler(commands=["exchange"])
    def exchange_menu(msg):
        text = (
            "📊 SLH Exchange\n\n"
            "🟢 קנייה:\n"
            "/buy_slh <amount_slh> <max_price_in_credits>\n\n"
            "🔴 מכירה:\n"
            "/sell_slh <amount_slh> <price_in_credits>\n\n"
            "📖 הוראות פתוחות:\n"
            "/orders\n\n"
            "📈 עסקאות אחרונות:\n"
            "/trades\n\n"
            "❌ ביטול הוראה:\n"
            "/cancel <order_id>"
        )
        bot.reply_to(msg, text)
