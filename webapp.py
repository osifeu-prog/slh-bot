from flask import Flask, jsonify, send_from_directory, request
import sqlite3, json, os

app = Flask(__name__, static_folder='web')
DB_NAME = "slh_empire.db"
CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE) as f: return json.load(f)
config = load_config()
ADMIN_ID = int(config.get("OWNER_ID",0))

@app.route("/")
def home(): return send_from_directory('web', 'index.html')

@app.route("/dashboard")
@app.route("/market")
def market(): return send_from_directory("web/dashboard", "market.html")
def dash(): return send_from_directory('web/dashboard', 'index.html')

@app.route("/api/status")
def status():
    conn=sqlite3.connect(DB_NAME)
    users=conn.cursor().execute("SELECT COUNT(*) FROM wallets").fetchone()[0]
    courses=conn.cursor().execute("SELECT COUNT(*) FROM academy_courses").fetchone()[0]
    conn.close()
    return jsonify({"users": users, "courses": courses, "status": "online", "admin_id": ADMIN_ID})

@app.route("/api/stats")
def stats(): return status()
@app.route("/api/health")
def health(): return jsonify({"status": "online"})

@app.route("/api/admin")
def admin_data():
    if request.args.get('id')!= str(ADMIN_ID): return jsonify({"error":"no auth"}), 403
    conn=sqlite3.connect(DB_NAME)
    users=conn.cursor().execute("SELECT user_id, wallet_balance FROM wallets").fetchall()
    commands = open("admin_menu.txt").read()
    conn.close()
    return jsonify({"users": users, "commands": commands})

@app.route("/api/exec", methods=["POST"])
def exec_cmd():
    if request.args.get('id')!= str(ADMIN_ID): return jsonify({"error":"no auth"}), 403
    cmd = request.json.get("command","")
    return jsonify({"result": f"✅ פקודה /{cmd} התקבלה. שולח לבוט...\n\n— SLH Empire 👑"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

# חנות ישירה בבוט
PRODUCTS = {
    "ai": {"name": "קורס AI Automation", "price_ton": 15, "price_ils": 499},
    "vip": {"name": "מנוי VIP חודשי", "price_ton": 5, "price_ils": 199}
}

@app.route("/api/buy", methods=["POST"])
def buy_product():
    data = request.json
    product_id = data.get("product")
    user_id = data.get("user_id")
    
    if product_id not in PRODUCTS:
        return jsonify({"error": "מוצר לא קיים"})
    
    p = PRODUCTS[product_id]
    wallet = "UQxxxxxxxxxxxxxxxxxxxxxxxxxx" # <- שים כאן ארנק TON שלך
    
    return jsonify({
        "product": p["name"],
        "amount_ton": p["price_ton"],
        "pay_link": f"ton://transfer/{wallet}?amount={p['price_ton']}&text=SLH-{user_id}-{product_id}",
        "instructions": "שלח ושלח לי צילום מסך לקבלת גישה"
    })
