"""Runtime command registry derived from the modules loaded by handlers.loader.

The registry is informational only. It never executes commands.
"""

from __future__ import annotations

import ast
import inspect


_COMMANDS: set[str] = set()


def _normalize(value) -> str | None:
    text = str(value or "").strip().lstrip("/").lower()
    return text or None


def _extract_commands(source: str) -> set[str]:
    found: set[str] = set()
    try:
        tree = ast.parse(source)
    except (SyntaxError, TypeError, ValueError):
        return found

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "message_handler":
            continue
        for keyword in node.keywords:
            if keyword.arg != "commands":
                continue
            try:
                value = ast.literal_eval(keyword.value)
            except (ValueError, TypeError, SyntaxError):
                continue
            if isinstance(value, str):
                value = [value]
            if isinstance(value, (list, tuple, set)):
                for command in value:
                    normalized = _normalize(command)
                    if normalized:
                        found.add(normalized)
    return found


def register_module(module) -> set[str]:
    try:
        source = inspect.getsource(module)
    except (OSError, TypeError):
        return set()
    commands = _extract_commands(source)
    _COMMANDS.update(commands)
    return commands


def reset() -> None:
    _COMMANDS.clear()


def get_registered_commands() -> set[str]:
    return set(_COMMANDS)


def get_registered_commands_text() -> str:
    commands = sorted(_COMMANDS)
    return ", ".join("/" + command for command in commands)
