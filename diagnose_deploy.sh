#!/data/data/com.termux/files/usr/bin/bash
echo "============================================="
echo "  SLH DEPLOYMENT DIAGNOSTIC"
echo "============================================="
echo ""

# 1. Git info
echo "[1] Git status"
echo "Branch: $(git branch --show-current)"
echo "Last commit:"
git log -1 --oneline
echo "Origin URL: $(git remote get-url origin)"
echo ""

# 2. Check if commit is on remote
echo "[2] Remote check"
REMOTE_SHA=$(git ls-remote origin HEAD | awk '{print $1}')
LOCAL_SHA=$(git rev-parse HEAD)
echo "Local SHA : $LOCAL_SHA"
echo "Remote SHA: $REMOTE_SHA"
if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    echo "✅ Commits match – push succeeded"
else
    echo "❌ Commits differ – push may have failed"
fi
echo ""

# 3. Railway API check
echo "[3] Railway deployment info"
TOKEN=$(cat ~/.railway_token)
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://backboard.railway.app/graphql/v2" \
  -d '{"query":"{ service(id: \"13d97581-0199-4f6a-80d1-885c9304ffc5\") { deployments(first: 1) { edges { node { id status createdAt meta } } } } }"}' | jq '.data.service.deployments.edges[0].node | {id, status, createdAt, branch: .meta.branch, commit: .meta.commitHash[:7], message: .meta.commitMessage}'
echo ""

# 4. Restart trigger
echo "[4] Triggering restart..."
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "https://backboard.railway.app/project/fd30fefb-3d35-48a5-a7cb-e05337e812c4/service/13d97581-0199-4f6a-80d1-885c9304ffc5/restart"
echo ""

echo "Done."
