from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/market')
def market():
    return jsonify({"status": "SLH Market UP", "time": "2026-07-29"}), 200

@app.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run()
