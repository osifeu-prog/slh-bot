from flask import Flask, jsonify, send_from_directory
from plugins import pm

app = Flask(__name__, static_folder='web')
pm.load_all()

@app.route("/")
def home():
    return send_from_directory('web', 'index.html')

@app.route("/api/courses")
def courses():
    return jsonify(pm.get("education").list_courses())

@app.route("/api/shop")
def shop():
    return jsonify(pm.get("shop").list_items())

@app.route("/api/status")
def status():
    import json
    db = json.load(open("state/db.json"))
    return jsonify({"users": len(db["users"]), "tasks": len(db["tasks"]), "credits": db["users"]["8789977826"]["credits"]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

from flask import request
import json

@app.route("/api/buy")
def buy():
    uid = request.args.get("uid")
    item = request.args.get("item")
    db = json.load(open("state/db.json"))
    result = pm.get("shop").buy(uid, item, db)
    json.dump(db, open("state/db.json", "w"), ensure_ascii=False, indent=2)
    return result
