import json, os

def register(bot):
    @bot.message_handler(commands=['stake'])
    def stake_cmd(msg):
        bot.reply_to(msg, "⏳ Staking module is being rebuilt. Check /balance for now.")
    
    @bot.message_handler(commands=['unstake'])
    def unstake_cmd(msg):
        bot.reply_to(msg, "⏳ Unstaking module is being rebuilt.")
