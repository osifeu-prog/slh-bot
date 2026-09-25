"""BNB / BSC deposit gate.

Closed unless BNB_DEPOSITS_OPEN=1.
While closed, no deposit surface may expose the treasury address or settle a claim.
"""
import os

CLOSED_MESSAGE = "\u26d4\ufe0f \u05d4\u05e4\u05e7\u05d3\u05d5\u05ea BNB/SLH \u05e1\u05d2\u05d5\u05e8\u05d5\u05ea \u05db\u05e8\u05d2\u05e2. \u05d0\u05dc \u05ea\u05e9\u05dc\u05d7 \u05e2\u05d3 \u05dc\u05d4\u05d5\u05d3\u05e2\u05d4."

def bnb_deposits_open() -> bool:
    return os.getenv("BNB_DEPOSITS_OPEN", "0").strip() == "1"
