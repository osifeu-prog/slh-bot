def register_api(app):
    from flask import request, jsonify
    import json, os
    @app.route('/get_tasks')
    def get_tasks():
        device = request.args.get('device')
        return jsonify({})
    @app.route('/result', methods=['POST'])
    def result():
        return jsonify({"status":"ok"})
