import json
with open("config.json") as f:
    print(json.load(f)["BOT_TOKEN"])
