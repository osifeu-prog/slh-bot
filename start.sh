#!/bin/bash

# Update token from Railway env var
if [ ! -z "$BOT_TOKEN" ]; then
  python3 << 'PYTHON'
import json
cfg = json.load(open("config.json"))
cfg["BOT_TOKEN"] = os.environ.get("BOT_TOKEN")
json.dump(cfg, open("config.json", "w"), indent=2)
PYTHON
fi

# Start bot
python3 -B bot.py
