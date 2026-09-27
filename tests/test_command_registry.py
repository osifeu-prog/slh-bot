from core import command_registry


def test_command_registry_extracts_message_handler_commands():
    command_registry.reset()
    source = '''
from telebot import TeleBot
bot = TeleBot("x")
@bot.message_handler(commands=["help", "share"])
def handler(message):
    pass
'''
    found = command_registry._extract_commands(source)
    assert found == {"help", "share"}


def test_unknown_command_filter_uses_runtime_registry():
    command_registry.reset()
    command_registry._COMMANDS.update({"help", "share"})
    from handlers.llm_handler import _sanitize_unknown_commands
    text = _sanitize_unknown_commands("השתמש ב-/share וב-/verify")
    assert "/share" in text
    assert "/verify" not in text
    assert "[פקודה לא רשומה]" in text
