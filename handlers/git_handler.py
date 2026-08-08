import os, requests, json, base64, hashlib

GITHUB_TOKEN = os.getenv('GIT_TOKEN')
REPO_OWNER = 'osifeu-prog'
REPO_NAME = 'slh-bot'
BRANCH = 'main'
BASE_DIR = '/app'
EXCLUDE = {'.git', '__pycache__', 'state', 'logs', 'venv', '.nixpacks'}
EXTENSIONS = {'.py', '.html', '.json', '.md', '.txt', '.yml', '.yaml', '.cfg', '.ini'}

def compute_blob_sha(content: bytes) -> str:
    header = f'blob {len(content)}\0'.encode()
    return hashlib.sha1(header + content).hexdigest()

def get_local_files():
    result = {}
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        for f in files:
            if not any(f.endswith(ext) for ext in EXTENSIONS):
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, BASE_DIR).replace('\\', '/')
            with open(path, 'rb') as fh:
                content = fh.read()
            result[rel] = {
                'content': content,
                'sha': compute_blob_sha(content)
            }
    return result

def register(bot):
    @bot.message_handler(commands=['git'])
    def git_cmd(msg):
        if str(msg.from_user.id) != os.getenv('ADMIN_ID', '8789977826'):
            bot.reply_to(msg, '⛔ Admin only')
            return
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(msg, 'Usage: /git commit <message>')
            return
        action = parts[1]
        message = parts[2] if len(parts) > 2 else ''
        if action != 'commit':
            bot.reply_to(msg, 'Only /git commit supported')
            return
        if not GITHUB_TOKEN:
            bot.reply_to(msg, '❌ GIT_TOKEN not set')
            return

        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # 1. Get latest commit & tree from GitHub
        ref_url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/{BRANCH}'
        r = requests.get(ref_url, headers=headers)
        if r.status_code != 200:
            bot.reply_to(msg, f'❌ GitHub error: {r.text[:200]}')
            return
        last_commit_sha = r.json()['object']['sha']

        commit_url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/commits/{last_commit_sha}'
        r = requests.get(commit_url, headers=headers)
        if r.status_code != 200:
            bot.reply_to(msg, f'❌ GitHub error: {r.text[:200]}')
            return
        base_tree_sha = r.json()['tree']['sha']

        # 2. Get the remote tree recursively
        def get_remote_tree(sha):
            tree = {}
            url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/{sha}?recursive=1'
            r = requests.get(url, headers=headers)
            if r.status_code != 200:
                return None
            for item in r.json().get('tree', []):
                if item['type'] == 'blob':
                    tree[item['path']] = item['sha']
            return tree

        remote_tree = get_remote_tree(base_tree_sha)
        if remote_tree is None:
            bot.reply_to(msg, '❌ Failed to fetch remote tree')
            return

        # 3. Scan local files and compare
        local_files = get_local_files()
        changed = []
        for path, info in local_files.items():
            if path not in remote_tree or info['sha'] != remote_tree[path]:
                changed.append(path)

        # Also detect deletions (optional)
        # for path in remote_tree:
        #    if path not in local_files:
        #        changed.append(path)  # deletion handling would need separate logic

        if not changed:
            bot.reply_to(msg, '✅ No changes to commit')
            return

        bot.reply_to(msg, f'📦 {len(changed)} files changed:\n' + '\n'.join(changed[:10]) + ('\n...' if len(changed)>10 else ''))

        # 4. Create blobs for changed files (only new/modified)
        new_tree_items = []
        for path in changed:
            content = local_files[path]['content']
            blob_url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/blobs'
            blob_data = {
                'content': base64.b64encode(content).decode('utf-8'),
                'encoding': 'base64'
            }
            r = requests.post(blob_url, json=blob_data, headers=headers)
            if r.status_code != 201:
                bot.reply_to(msg, f'❌ Blob failed for {path}: {r.text[:100]}')
                return
            new_tree_items.append({
                'path': path,
                'mode': '100644',
                'type': 'blob',
                'sha': r.json()['sha']
            })

        # 5. Create new tree
        tree_url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/trees'
        tree_data = {
            'base_tree': base_tree_sha,
            'tree': new_tree_items
        }
        r = requests.post(tree_url, json=tree_data, headers=headers)
        if r.status_code != 201:
            bot.reply_to(msg, f'❌ Tree failed: {r.text[:100]}')
            return
        new_tree_sha = r.json()['sha']

        # 6. Create commit
        commit_data = {
            'message': message,
            'tree': new_tree_sha,
            'parents': [last_commit_sha]
        }
        r = requests.post(commit_url, json=commit_data, headers=headers)
        if r.status_code != 201:
            bot.reply_to(msg, f'❌ Commit failed: {r.text[:100]}')
            return
        new_commit_sha = r.json()['sha']

        # 7. Update branch reference
        r = requests.patch(ref_url, json={'sha': new_commit_sha, 'force': False}, headers=headers)
        if r.status_code == 200:
            bot.reply_to(msg, f'✅ Committed & pushed: {message}')
        else:
            bot.reply_to(msg, f'❌ Ref update failed: {r.text[:100]}')
