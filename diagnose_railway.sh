#!/data/data/com.termux/files/usr/bin/bash
TOKEN=$(cat ~/.railway_token)
echo "=== Test direct API call ==="
# Test a simple query
RESP=$(curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://backboard.railway.app/graphql/v2" \
  -d '{"query":"{ viewer { id } }"}')
echo "$RESP" | jq .
# If viewer works, try projects
echo ""
echo "=== Projects ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://backboard.railway.app/graphql/v2" \
  -d '{"query":"{ projects { edges { node { id name } } } }"}' | jq .
