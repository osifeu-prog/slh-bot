from pathlib import Path

p = Path("handlers/llm_handler.py")
s = p.read_text(encoding="utf-8")

# add import
if "from core.ai_guard import" not in s:
    s = s.replace(
        "from groq import Groq",
        "from groq import Groq\nfrom core.ai_guard import provider_available, provider_success, provider_failure"
    )

old = '''def query_llm(question):
    """
    Main LLM gateway for ASK.
    """
    client = get_client()

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are SLH OS AI assistant. Answer in Hebrew when possible."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        max_tokens=500
    )

    return response.choices[0].message.content
'''

new = '''def query_llm(question):
    """
    Main LLM gateway for ASK.
    """

    if not provider_available("groq"):
        return "⏳ שירות ה-AI בהשהיה זמנית. נסה שוב בעוד מספר דקות."

    try:
        client = get_client()

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are SLH OS AI assistant. Answer in Hebrew when possible."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            max_tokens=500
        )

        provider_success("groq")

        return response.choices[0].message.content

    except Exception as e:
        provider_failure("groq")
        raise e
'''

if old in s:
    s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("LLM circuit breaker connected")
else:
    print("query_llm block not found")
