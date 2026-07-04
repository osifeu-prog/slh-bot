import json

def get_token():
    with open("config.json") as f:
        return json.load(f)["BOT_TOKEN"]

if __name__ == "__main__":
    # רק כשמריצים ישירות, לא כשמייבאים
    print(get_token())
