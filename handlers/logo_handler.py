from handlers.onboarding_v2 import load_branding
from core.message_utils import safe_clip


def register_logo_handler(bot):
    @bot.message_handler(commands=['logo', 'brand'])
    def logo_cmd(msg):
        branding = load_branding(bot)
        bot.reply_to(msg, f"<pre>{safe_clip(branding, 1200)}</pre>", parse_mode="HTML")
