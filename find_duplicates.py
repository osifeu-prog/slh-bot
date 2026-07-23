import re, os

legacy = set()
modern = set()

with open('bot_stable.py', encoding='utf-8') as f:
    s = f.read()
    for x in re.findall(r'commands=\[([^\]]+)\]', s):
        for c in re.findall(r'[\'"]([a-zA-Z0-9_]+)[\'"]', x):
            legacy.add(c)

for root, dirs, files in os.walk('handlers'):
    for fname in files:
        if fname.endswith('.py'):
            path = os.path.join(root, fname)
            try:
                with open(path, encoding='utf-8') as f:
                    s = f.read()
                    for x in re.findall(r'commands=\[([^\]]+)\]', s):
                        for c in re.findall(r'[\'"]([a-zA-Z0-9_]+)[\'"]', x):
                            modern.add(c)
            except:
                pass

duplicates = sorted(legacy & modern)

print('===== DUPLICATE OWNERSHIP =====')
for c in duplicates:
    print('/' + c)

print()
print('LEGACY:', len(legacy))
print('MODERN:', len(modern))
print('DUPLICATES:', len(duplicates))