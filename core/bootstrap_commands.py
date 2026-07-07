from core.command_router import register_command

# כאן אתה מחבר את כל ה-handlers בפועל
# כל מודול צריך לחשוף פונקציה בשם register(reg)

import ask_handler
import admin_handler
from plugins import task as task_handler
import learn_handlers
import course_handlers
import project_commands
import monitor_handler
import report_handler
import help_handler

def init():
    modules = [
        ask_handler,
        admin_handler,
        task_handler,
        learn_handlers,
        course_handlers,
        project_commands,
        monitor_handler,
        report_handler,
        help_handler
    ]

    for m in modules:
        if hasattr(m, "register"):
            m.register(register_command)
