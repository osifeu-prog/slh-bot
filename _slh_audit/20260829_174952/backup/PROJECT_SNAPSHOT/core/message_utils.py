def safe_clip(text, limit=3500):
    if text is None:
        return ""

    text = str(text)

    if len(text) <= limit:
        return text

    return text[:limit] + "\n\n...[truncated]"
