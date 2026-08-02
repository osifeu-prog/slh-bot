#!/data/data/com.termux/files/usr/bin/bash

cd ~/slh_clean || exit 1

TOKEN="$1"

if [ -z "$TOKEN" ]; then
  echo "USAGE: ./token_sync.sh NEW_TOKEN"
  exit 1
fi

python3 - << PY
import json, os
from datetime import datetime

state_file="state/system.json"
os.makedirs("state", exist_ok=True)

data={}
if os.path.exists(state_file):
    try:
        data=json.load(open(state_file))
    except:
        pass

data["BOT_TOKEN"]="$TOKEN"
data["updated"]=datetime.now().isoformat()

json.dump(data, open(state_file,"w"), indent=2)
PY

echo "TOKEN SAVED -> RESTART REQUIRED"
