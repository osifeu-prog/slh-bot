
import os, sys, json, base64, urllib.request, urllib.parse

OWNER = os.environ.get("RAILWAY_GIT_REPO_OWNER") or "osifeu-prog"
REPO = os.environ.get("RAILWAY_GIT_REPO_NAME") or "slh-bot"
BRANCH = os.environ.get("RAILWAY_GIT_BRANCH") or "main"
TOKEN = os.environ.get("GIT_TOKEN")

if not TOKEN:
    print("MISSING_GIT_TOKEN")
    raise SystemExit(1)

BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"


def api(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def get_ref():
    return api("GET", f"/git/ref/heads/{BRANCH}")


def commit_files(files, message):
    ref = get_ref()
    base_sha = ref["object"]["sha"]
    base_commit = api("GET", f"/git/commits/{base_sha}")
    base_tree = base_commit["tree"]["sha"]

    tree_items = []

    for path in files:
        with open(path, "rb") as f:
            content = f.read()

        blob = api("POST", "/git/blobs", {
            "content": base64.b64encode(content).decode(),
            "encoding": "base64"
        })

        tree_items.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"]
        })

    new_tree = api("POST", "/git/trees", {
        "base_tree": base_tree,
        "tree": tree_items
    })

    new_commit = api("POST", "/git/commits", {
        "message": message,
        "tree": new_tree["sha"],
        "parents": [base_sha]
    })

    api("PATCH", f"/git/refs/heads/{BRANCH}", {
        "sha": new_commit["sha"],
        "force": False
    })

    print("COMMIT_PUSHED", new_commit["sha"])


if __name__ == "__main__":
    args = sys.argv[1:]
    message = None
    files = []

    if "-m" in args:
        i = args.index("-m")
        message = args[i + 1]
        files = args[:i] + args[i + 2:]
    else:
        print("Usage: python3 exec_commit.py -m MESSAGE file1 file2 ...")
        raise SystemExit(1)

    commit_files(files, message)
