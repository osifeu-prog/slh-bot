"""Canonical bounded intake for the SLH assistant."""

from __future__ import annotations

AI_MAX_INPUT_CHARS = 12000
AI_CHUNK_CHARS = 1500


def normalize_and_chunk(text: str) -> str:
    value = (
        str(text or "")
        .replace("\x00", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )
    if len(value) > AI_MAX_INPUT_CHARS:
        raise ValueError("AI_INPUT_TOO_LONG")

    if len(value) <= AI_CHUNK_CHARS:
        return value

    chunks = [
        value[i : i + AI_CHUNK_CHARS]
        for i in range(0, len(value), AI_CHUNK_CHARS)
    ]
    total = len(chunks)
    return "\n\n".join(
        f"[AI_INPUT_CHUNK {idx}/{total}]\n{chunk}"
        for idx, chunk in enumerate(chunks, start=1)
    )
