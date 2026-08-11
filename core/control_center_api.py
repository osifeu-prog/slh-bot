from flask import jsonify
from core.control_center import get_system_snapshot

def register_control_center(app):

    @app.route("/control-center")
    def control_center():

        return jsonify(
            get_system_snapshot()
        )
