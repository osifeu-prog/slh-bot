import json
with open(r'C:\Users\USER\slh-bot-clean\state\db.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
users = len(d.get('users', {}))
agents = len(d.get('agents', {}))
tasks = len(d.get('tasks', []))
print(f'Users: {users} | Agents: {agents} | Tasks: {tasks}')
