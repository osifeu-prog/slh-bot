import json
with open('state/journal.json', 'r', encoding='utf-8') as f:
    j = json.load(f)
entries = j[0].get('entries', {}).get('entries', [])
for e in entries[-5:]:
    ts = e.get('time') or e.get('timestamp') or e.get('date','?')
    txt = e.get('text') or e.get('summary') or e.get('details','?')
    print(f'{str(ts)[:10]} - {str(txt)[:80]}')
