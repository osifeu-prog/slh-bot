import json, os
from flask import request, jsonify

def register_api(app):
    @app.route('/get_tasks')
    def get_tasks():
        device = request.args.get('device')
        if os.path.exists('state/tasks.json'):
            with open('state/tasks.json') as f: t=json.load(f)
            return jsonify(t.get(device, {}))
        return jsonify({})

    @app.route('/result', methods=['POST'])
    def result():
        data = request.json
        with open('state/results.json','a') as f: f.write(json.dumps(data)+"\n")
        return jsonify({"status":"ok"})
