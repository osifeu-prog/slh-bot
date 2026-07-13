import subprocess as sp

def init(bot):
    @bot.message_handler(commands=['ask'])
    def ask(m):
        question = m.text.replace('/ask', '').strip()
        if not question:
            bot.reply_to(m, "Usage: /ask <your question>")
            return
        try:
            result = sp.check_output(["ollama", "run", "phi3:mini", "ענה בעברית, בפסקה קצרה: " + question], text=True, timeout=120)
            bot.reply_to(m, result[:4000])
        except sp.TimeoutExpired:
            bot.reply_to(m, "❌ Timeout (try again)")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")
