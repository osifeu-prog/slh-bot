#!/bin/bash
cd ~/slh_clean
clear
cat logo.txt 2>/dev/null || echo "SLH OS"
echo ""
echo "======================================="
echo "   SLH Morning Dashboard"
echo "======================================="
echo ""

echo "🚂 Railway:"
railway status 2>/dev/null | grep -E "status:|deployment ID:"
echo ""

echo "📓 Latest journal entry:"
python3 -c "
import json
try:
    with open('journal.json', encoding='utf-8') as f:
        entries = json.load(f)
    if entries:
        last = entries[-1]
        print('  ', last.get('time', ''))
        text = last.get('text', '')
        print('  ', text[:200] + ('...' if len(text) > 200 else ''))
    else:
        print('   (no entries)')
except Exception as e:
    print('   Error:', e)
"
echo ""

echo "📋 Open tasks (from Railway live DB):"
railway ssh -- "python3 -c \"
import json
d = json.load(open('/app/state/db.json'))
tasks = d.get('user_tasks', {}).get('8789977826', [])
if tasks:
    for i, t in enumerate(tasks, 1):
        print(f'   {i}. {t}')
else:
    print('   (no tasks)')
\"" 2>/dev/null
echo ""

echo "======================================="
echo "Commands: railway status | railway logs --tail 50"
echo "======================================="

# תפריט 5 אפשרויות
select opt in "🟢 הפעל מערכת" "🔴 עצור מערכת" "📊 מצב מערכת" "🚂 לוגים Railway" "🚪 יציאה"; do
    case $opt in
        "🟢 הפעל מערכת") ~/slh_clean/slh start; break;;
        "🔴 עצור מערכת") ~/slh_clean/slh stop; break;;
        "📊 מצב מערכת") ~/slh_clean/slh status; break;;
        "🚂 לוגים Railway") railway logs --tail 20; break;;
        "🚪 יציאה") break;;
    esac
done
