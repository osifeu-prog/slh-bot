import state_manager

def init(bot):
    @bot.message_handler(commands=['stake'])
    def stake(m):
        bot.send_message(m.chat.id, """🔰 Staking 4% חודשי
/stake_join <amount> USDT""")

    @bot.message_handler(commands=['stake_join'])
    def stake_join(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /stake_join <amount>")
            return
        amount = parts[1]
        bot.reply_to(m, f"✅ Staked {amount} USDT at 4% monthly!")

    @bot.message_handler(commands=['pnl'])
    def pnl(m):
        bot.send_message(m.chat.id, "📊 PnL: -1310$\nTrades: 36\nWin Rate: 58%")

    @bot.message_handler(commands=['staking_report'])
    def staking_report(m):
        bot.send_message(m.chat.id, """📊 מאזן מלא:
Total Staked: 0 USDT
Your Balance: 0 USDT
ROI: 4% חודשי
Investors: 2""")
