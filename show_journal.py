from pathlib import Path
import json

JOURNAL = Path("state/journal.json")

data = json.loads(JOURNAL.read_text(encoding="utf-8"))

print("="*70)
print("SLH JOURNAL HISTORY")
print("="*70)

entries = []

for item in data:
    if isinstance(item, dict):
        if "entries" in item:
            inner = item["entries"].get("entries", [])
            entries.extend(inner)
        else:
            entries.append(item)

for e in entries[-10:]:
    t = e.get("time") or e.get("timestamp") or e.get("date")
    text = e.get("text") or e.get("summary") or e.get("details")
    print()
    print(t)
    print(str(text)[:300])

print()
print("TOTAL EVENTS:", len(entries))
print("="*70)
