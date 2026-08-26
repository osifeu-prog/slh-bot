from core.reconciler import reconcile

def register(bot):
    @bot.message_handler(commands=["reconcile"])
    def reconcile_cmd(msg):
        bot.reply_to(msg, reconcile())
