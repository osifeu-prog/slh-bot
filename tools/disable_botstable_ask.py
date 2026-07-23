from pathlib import Path

p = Path("bot_stable.py")
s = p.read_text(encoding="utf-8")

old = '''@bot.message_handler(commands=['ask'])
def ask_cmd(m):
    question = m.text.replace('/ask', '').strip()
    if not question:
        bot.reply_to(m, "Usage: /ask <your question>")
        return
    from core.ask_router import route as ask_route
    local_answer = ask_route(question)
    if local_answer:
        bot.reply_to(m, local_answer)
        return
    try:
        from handlers.llm_handler import query_llm
        from core.context_builder import get_context
        ctx = get_context()
'''

if old in s:
    s = s.replace(
        "@bot.message_handler(commands=['ask'])",
        "# DISABLED: ASK moved to advanced_ask_handler.py\n# @bot.message_handler(commands=['ask'])",
        1
    )
    p.write_text(s, encoding="utf-8")
    print("ASK duplicate handler disabled")
else:
    print("ASK block signature not found - no change")
