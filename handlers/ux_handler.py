def register(bot):
    @bot.message_handler(commands=['ux'])
    def ux_menu(msg):
        text = """🎨 SLH OS UI/UX Dashboard

/screens – List all screens
/preview <screen> – Preview screen
/colors – Color palette
/logo – Get current logo
/export – Export UI assets

🛠 UI/UX Team Tools:
• Figma: [link coming]
• Assets: branding/
• Web: web-production-22f28.up.railway.app
"""
        bot.reply_to(msg, text)

    @bot.message_handler(commands=['screens'])
    def screens(msg):
        screens = [
            "🏠 /start – Welcome screen",
            "📊 /dashboard – Admin dashboard",
            "📚 /academy – Academy view",
            "💰 /wallet – Wallet view",
            "🤖 /agents – Agent management",
            "🗳 /vote – Voting screen",
            "📓 /journal – Journal view"
        ]
        bot.reply_to(msg, "\n".join(screens))

    @bot.message_handler(commands=['colors'])
    def colors(msg):
        bot.reply_to(msg, """🎨 SLH Color Palette
Primary: Cyan (#00FFFF)
Secondary: Yellow (#FFFF00)
Accent: Green (#00FF00)
Background: Black (#000000)
Text: White (#FFFFFF)
""")

    print("✅ ux_handler loaded")
