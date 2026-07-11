def register(bot):
    @bot.message_handler(commands=['tutorial'])
    def tutorial(m):
        text = """📖 **SLH – הדרכה מהירה**

1️⃣ **הרשמה** – /join
2️⃣ **התחל קורס** – /courses → /start_course <id>
3️⃣ **צור סוכן** – /agent_create <שם>
4️⃣ **הרווח קרדיטים** – /pay
5️⃣ **דו"ח יומי** – /endday

🔍 **צפייה בקבצים** – /viewfile <path>
🛠 **שליטה** – /admin לניהול

❓ **שאלות?** – /ask <שאלה>"""
        bot.reply_to(m, text, parse_mode="Markdown")
