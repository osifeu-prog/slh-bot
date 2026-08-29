"""Placeholder for device bridge API"""
def register_api(app):
    from flask import request, jsonify
    
    @app.route('/get_tasks')
    def get_tasks():
        device = request.args.get('device', 'unknown')
        return jsonify({"tasks":[]})
    
    @app.route('/result', methods=['POST'])
    def result():
        return jsonify({"status":"ok", "note":"placeholder active"})
    
    @app.route('/register_esp', methods=['POST'])
    def register():
        return jsonify({"status":"ok", "msg":"device registered"})
    
    print("✅ device_bridge placeholder loaded")
