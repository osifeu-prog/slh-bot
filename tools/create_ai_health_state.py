from pathlib import Path
import json

p = Path("state/ai_health.json")

if not p.exists():
    p.write_text(
        json.dumps(
            {
                "groq": {
                    "failures": 0,
                    "blocked_until": 0
                }
            },
            indent=2
        ),
        encoding="utf-8"
    )

print("AI health state created")
