from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler

TOKEN = "שים_כאן_את_הTOKEN_שלך_מ_BotFather"
WEBAPP_URL = "https://TEMP_LINK.cloudflared.com" # נחליף אחר כך

async def start(update: Update, context):
    keyboard = [[KeyboardButton("פתח אימפריה 👑", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        "ברוך הבא לאימפריה",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.run_polling()
