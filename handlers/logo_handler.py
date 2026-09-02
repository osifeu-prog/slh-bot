from handlers.onboarding_v2 import load_branding


def register_logo_handler(bot):
    @bot.message_handler(commands=['logo', 'brand'])
    def logo_cmd(msg):
        branding = load_branding()
        bot.reply_to(msg, f"<pre>{branding}</pre>", parse_mode="HTML")
