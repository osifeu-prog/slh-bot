import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.ask_router import route as ask_route
from core.ask_guard import allow_request, guarded_message
import tempfile

# ===== FILE HANDLING HELPERS =====
def download_file(bot, file_id):
    """Download a file from Telegram and return its content as text."""
    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        # Try to decode as text (TXT)
        try:
            return downloaded_file.decode('utf-8')
        except UnicodeDecodeError:
            # If it's PDF, we might need a library, but we'll return a placeholder
            return "[PDF file detected – content not readable without external library]"
    except Exception as e:
        return f"[Error downloading file: {e}]"

def handle_file_message(msg, bot):
    """Handle a message that contains a file (document)."""
    document = msg.document
    if not document:
        return None
    file_name = document.file_name or "unknown"
    file_id = document.file_id
    # Download and read
    content = download_file(bot, file_id)
    if content.startswith("[PDF"):
        return f"📄 קובץ: {file_name}\n{content}"
    else:
        # Build a prompt with the file content
        return f"קובץ: {file_name}\n\nתוכן הקובץ:\n{content[:3000]}\n\n---\nמה תרצה לדעת על הקובץ הזה?"

# ===== MAIN HANDLER =====
def register_ask_handler(bot, context):
    @bot.message_handler(commands=['ask'])
    def ask(msg):
        # Check if there is a document attached
        if hasattr(msg, 'document') and msg.document:
            file_content = handle_file_message(msg, bot)
            if file_content:
                # Use the file content as the question
                question = file_content
            else:
                bot.reply_to(msg, "⚠️ לא הצלחתי לקרוא את הקובץ.")
                return
        else:
            # Regular text question
            question = msg.text.replace('/ask', '').strip()
            if not question:
                bot.reply_to(msg, "Usage: /ask <your question> (or attach a file)")
                return

        # Guard check
        if not allow_request(question):
            bot.reply_to(msg, guarded_message())
            return

        # Try local router
        local_answer = ask_route(question)
        if local_answer:
            bot.reply_to(msg, local_answer)
            return

        # Fallback to LLM
        try:
            from handlers.llm_handler import query_llm
            from core.context_builder import get_context
            ctx = get_context()
            system_msg = "אתה SLH OS Assistant. המצב הנוכחי:\n"
            for k, v in ctx.items():
                system_msg += f"- {k}: {v}\n"
            prompt = f"{system_msg}\n\nשאלת המשתמש: {question}\n\nענה בעברית תמציתית."
            answer = query_llm(prompt)
            bot.reply_to(msg, answer)
        except Exception as e:
            bot.reply_to(msg, f"⚠️ כל מנועי ה-AI עמוסים כרגע ({e}). נסה שוב מאוחר יותר.")

    # ===== OPTIONAL: readfile command =====
    @bot.message_handler(commands=['readfile'])
    def readfile_cmd(msg):
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /readfile <path>")
            return
        path = parts[1].strip()
        # Security: only allow files in safe directories
        safe_dirs = ["state/uploads", "state/reports", "state/logs"]
        abs_path = os.path.abspath(path)
        safe = any(abs_path.startswith(os.path.abspath(d)) for d in safe_dirs)
        if not safe:
            bot.reply_to(msg, "❌ Access denied. Only files in state/uploads, state/reports, state/logs are allowed.")
            return
        if not os.path.exists(path):
            bot.reply_to(msg, f"❌ File not found: {path}")
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if len(content) > 4000:
                content = content[:4000] + "\n... (truncated)"
            bot.reply_to(msg, f"📄 **{path}**\n\n{content}", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(msg, f"❌ Error reading file: {e}")