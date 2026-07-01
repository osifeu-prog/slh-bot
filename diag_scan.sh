#!/usr/bin/env bash
cd ~/slh_clean
echo "🔍 SLH Backend Scan"
echo "==================="
echo "📁 Active Python files:"
find . -maxdepth 2 -name '*.py' ! -name '*backup*' ! -name '*bak*' ! -path './backup*' ! -path './archive*' ! -path './slh_v9*' | sort
echo ""
echo "📁 Lessons:"
find lessons -type f 2>/dev/null
echo ""
echo "📁 DB sections:"
python3 -c "
import json; db=json.load(open('db.json'))
for k,v in db.items():
    if isinstance(v, dict): print(f'  {k}: {len(v)} items')
    elif isinstance(v, list): print(f'  {k}: {len(v)} items')
    else: print(f'  {k}: {v}')
"
echo "📁 Courses:"
python3 -c "import json; d=json.load(open('courses.json')); [print(f'  {k}: {len(v.get(\"stages\",[]))} stages') for k,v in d.items()]"
echo "📊 self_test:"
python3 -c "from self_test import test_all; [print(f'  {n}: {s}') for n,s in test_all()]"
