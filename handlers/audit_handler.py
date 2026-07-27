from core.audit import read_events


MAX_MESSAGE_LENGTH = 3500


def _format_event(event):
    timestamp = event.get("timestamp", "")
    timestamp = timestamp.replace("T", " ")[:19]

    event_name = event.get("event", "unknown")
    actor = event.get("actor")
    target = event.get("target")
    details = event.get("details")

    lines = [
        f"🕒 {timestamp}",
        f"🔹 {event_name}",
    ]

    if actor is not None:
        lines.append(f"👤 Actor: {actor}")

    if target is not None:
        lines.append(f"🎯 Target: {target}")

    if details is not None:
        if isinstance(details, dict):
            detail_text = ", ".join(
                f"{key}={value}"
                for key, value in details.items()
            )
        else:
            detail_text = str(details)

        lines.append(f"📦 {detail_text}")

    return "\n".join(lines)


def _chunk_text(text, max_length=MAX_MESSAGE_LENGTH):
    chunks = []
    current = []

    current_length = 0

    for block in text.split("\n\n"):
        block_length = len(block) + 2

        if current and current_length + block_length > max_length:
            chunks.append("\n\n".join(current))
            current = []
            current_length = 0

        current.append(block)
        current_length += block_length

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def register(bot, context):

    @bot.message_handler(commands=["logs"])
    def logs_cmd(message):

        parts = message.text.split()

        limit = 20

        if len(parts) >= 2:
            try:
                limit = int(parts[1])
            except ValueError:
                bot.reply_to(
                    message,
                    "❌ Usage: /logs [number]"
                )
                return

        limit = max(1, min(limit, 100))

        events = read_events(limit)

        if not events:
            bot.reply_to(
                message,
                "🛰 AUDIT LOG\n\nNo events recorded."
            )
            return

        blocks = [
            _format_event(event)
            for event in events
        ]

        text = (
            f"🛰 AUDIT LOG — LAST {len(events)}\n\n"
            + "\n\n".join(blocks)
        )

        for chunk in _chunk_text(text):
            bot.reply_to(message, chunk)
