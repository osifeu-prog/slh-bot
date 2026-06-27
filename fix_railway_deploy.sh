#!/data/data/com.termux/files/usr/bin/bash
echo "============================================="
echo "  RAILWAY DEPLOY FIX"
echo "============================================="
echo ""

# 1. Check Railway token
if [ ! -f ~/.railway_token ]; then
    echo "❌ Railway token not found"
    echo "Go to: https://railway.app/account/tokens"
    echo "Create API token and save to ~/.railway_token"
    exit 1
fi
TOKEN=$(cat ~/.railway_token)
echo "✅ Railway token found"
echo ""

# 2. Current Git info
echo "📦 Git status:"
echo "Branch: $(git branch --show-current)"
echo "Last commit: $(git log -1 --oneline)"
echo "Remote SHA: $(git ls-remote origin HEAD | awk '{print $1}')"
echo ""

# 3. Railway service info
echo "📊 Railway service status:"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://backboard.railway.app/graphql/v2" \
  -d '{"query":"{ service(id: \"13d97581-0199-4f6a-80d1-885c9304ffc5\") { id name deployments(first:1) { edges { node { id status createdAt meta } } } } }"}' | jq '.data.service.deployments.edges[0].node | {id, status, createdAt, branch: .meta.branch, commit: .meta.commitHash[:7]}'
echo ""

# 4. Trigger restart (correct mutation for Railway v2)
echo "🔄 Triggering restart..."
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://backboard.railway.app/graphql/v2" \
  -d '{"query":"mutation { deploymentRestart(input: {serviceId: \"13d97581-0199-4f6a-80d1-885c9304ffc5\"}) { deployment { id status } } }"}' | jq .
echo ""

# 5. Trigger redeploy via empty commit
echo "📤 Triggering redeploy via empty commit..."
git commit --allow-empty -m "trigger: force Railway redeploy $(date +%s)"
git push
echo ""

echo "✅ Actions completed"
echo ""
echo "📋 Next steps:"
echo "1. Wait 30-60 seconds"
echo "2. Check Railway dashboard: https://railway.app/project/fd30fefb-3d35-48a5-a7cb-e05337e812c4/service/13d97581-0199-4f6a-80d1-885c9304ffc5"
echo "3. Look for deployment status: BUILDING → DEPLOYING → SUCCESS"
echo "4. If still stuck, click 'Deploy Now' button in Railway dashboard"
echo ""
echo "🔍 To monitor logs:"
echo "railway logs 13d97581-0199-4f6a-80d1-885c9304ffc5"
