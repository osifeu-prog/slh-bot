from pathlib import Path
from unittest.mock import patch

from core import esp_license


LICENSE_ID = "SLH-LIC-ABCDEF123456"
DEVICE_ID = "ESP32_SOSY_HARDWARE_01"
OWNER_UID = "8789977826"
SECRET_PASSWORD = "device-password-value-for-test"
SECRET_ACTIVATION = "SLH-ACT-ABCDEF12"


def seeded_state():
    db = {
        "users": {OWNER_UID: {"credits": 1.0}},
        "esp_licenses": {
            LICENSE_ID: {
                "license_id": LICENSE_ID,
                "device_id": DEVICE_ID,
                "owner_id": OWNER_UID,
                "status": "sold",
                "activation_code": SECRET_ACTIVATION,
                "mqtt_username": "esp_test",
                "mqtt_password": SECRET_PASSWORD,
                "activated_at": None,
            }
        },
        "purchases": {
            "purchase:telegram_buy:8789977826:190947": {
                "kind": "test_bill",
                "device_id": DEVICE_ID,
                "license_id": LICENSE_ID,
                "activation_code": SECRET_ACTIVATION,
                "mqtt_password": SECRET_PASSWORD,
            },
            "unrelated_purchase": {
                "kind": "other",
                "activation_code": "keep-this-unrelated-code",
                "mqtt_password": "keep-this-unrelated-password",
            },
            "new_license_purchase_same_device": {
                "kind": "device_license",
                "device_id": DEVICE_ID,
                "license_id": "SLH-LIC-FEDCBA654321",
                "activation_code": "new-license-activation",
                "mqtt_password": "new-device-password",
            },
        },
        "ledger": [{"uid": OWNER_UID, "amount": 1.0, "reason": "unrelated"}],
        "esp_license_security_audit": [],
    }
    devices = {
        "devices": {
            DEVICE_ID: {
                "owner": OWNER_UID,
                "license_key": LICENSE_ID,
                "license_status": "sold",
                "activation_code": SECRET_ACTIVATION,
            }
        }
    }
    return db, devices


def _patch_state(db, devices):
    def mutate_db(mutator):
        return mutator(db)

    def mutate_devices(filename, mutator, default=None):
        return mutator(devices)

    return (
        patch("core.esp_license.state_manager.atomic_update", side_effect=mutate_db),
        patch("core.esp_license.state_manager.load_json", return_value=devices),
        patch("core.esp_license.state_manager.atomic_json_update", side_effect=mutate_devices),
    )


def test_owner_revocation_removes_esp_secrets_from_license_purchase_and_device_state():
    db, devices = seeded_state()
    with patch("core.esp_license.is_owner", return_value=True), _patch_state(db, devices)[0], _patch_state(db, devices)[1], _patch_state(db, devices)[2]:
        result = esp_license.revoke_license(LICENSE_ID, actor_uid=OWNER_UID)

    assert result["status"] == "REVOKED"
    assert result["device_id"] == DEVICE_ID
    assert result["secrets_removed"] == ["activation_code", "mqtt_password"]
    assert SECRET_ACTIVATION not in repr(db)
    assert SECRET_PASSWORD not in repr(db)
    assert SECRET_ACTIVATION not in repr(devices)
    assert SECRET_PASSWORD not in repr(devices)

    revoked = db["esp_licenses"][LICENSE_ID]
    assert revoked["status"] == "revoked"
    assert revoked["revoked_at"]
    assert "activation_code" not in revoked
    assert "mqtt_password" not in revoked

    purchase = db["purchases"]["purchase:telegram_buy:8789977826:190947"]
    assert "activation_code" not in purchase
    assert "mqtt_password" not in purchase
    unrelated = db["purchases"]["unrelated_purchase"]
    assert unrelated["activation_code"] == "keep-this-unrelated-code"
    assert unrelated["mqtt_password"] == "keep-this-unrelated-password"
    new_license = db["purchases"]["new_license_purchase_same_device"]
    assert new_license["activation_code"] == "new-license-activation"
    assert new_license["mqtt_password"] == "new-device-password"

    device = devices["devices"][DEVICE_ID]
    assert device["license_status"] == "revoked"
    assert "activation_code" not in device
    assert db["ledger"] == [{"uid": OWNER_UID, "amount": 1.0, "reason": "unrelated"}]
    assert db["users"][OWNER_UID]["credits"] == 1.0

    audit = db["esp_license_security_audit"][-1]
    assert audit["action"] == "license_revoked_and_secrets_scrubbed"
    assert audit["actor_uid"] == OWNER_UID
    assert SECRET_PASSWORD not in repr(audit)
    assert SECRET_ACTIVATION not in repr(audit)


def test_non_owner_cannot_revoke_a_license():
    db, devices = seeded_state()
    with patch("core.esp_license.is_owner", return_value=False), _patch_state(db, devices)[0] as atomic_update:
        result = esp_license.revoke_license(LICENSE_ID, actor_uid="224223270")

    assert result["status"] == "FORBIDDEN"
    atomic_update.assert_not_called()
    assert db["esp_licenses"][LICENSE_ID]["status"] == "sold"
    assert db["esp_licenses"][LICENSE_ID]["mqtt_password"] == SECRET_PASSWORD


def test_revoked_license_cannot_be_activated_with_old_activation_code():
    db, devices = seeded_state()
    db["esp_licenses"][LICENSE_ID]["status"] = "revoked"
    db["esp_licenses"][LICENSE_ID].pop("activation_code")
    with patch("core.esp_license._load_json", side_effect=[db, devices]):
        result = esp_license.activate_license(DEVICE_ID, SECRET_ACTIVATION)

    assert result == {"ok": False, "error": "LICENSE_REVOKED"}


def test_issuing_after_revocation_creates_a_new_current_license():
    db, devices = seeded_state()
    old = db["esp_licenses"][LICENSE_ID]
    old["status"] = "revoked"
    old.pop("activation_code")
    old.pop("mqtt_password")
    state = {"db": db, "devices": devices}

    def load_json(path, default):
        return state["db"] if Path(path) == Path(esp_license.DB_PATH) else state["devices"]

    def save_json(path, data):
        if Path(path) == Path(esp_license.DB_PATH):
            state["db"] = data
        else:
            state["devices"] = data

    with patch("core.esp_license._load_json", side_effect=load_json), patch(
        "core.esp_license._save_json", side_effect=save_json
    ):
        issued = esp_license.issue_license(DEVICE_ID, OWNER_UID, duration_days=30)

    assert issued["ok"] is True
    assert issued["already_exists"] is False
    new_id = issued["license"]["license_id"]
    assert new_id != LICENSE_ID
    assert state["db"]["esp_licenses"][LICENSE_ID]["status"] == "revoked"
    assert state["devices"]["devices"][DEVICE_ID]["license_key"] == new_id
    assert state["devices"]["devices"][DEVICE_ID]["license_status"] == "sold"

    with patch("core.esp_license._load_json", side_effect=load_json), patch(
        "core.esp_license._save_json", side_effect=save_json
    ):
        activated = esp_license.activate_license(DEVICE_ID, issued["license"]["activation_code"])

    assert activated["ok"] is True
    assert state["db"]["esp_licenses"][new_id]["status"] == "activated"


def test_get_license_returns_the_current_device_license_not_a_revoked_old_one():
    db, devices = seeded_state()
    db["esp_licenses"][LICENSE_ID]["status"] = "revoked"
    db["esp_licenses"][LICENSE_ID].pop("activation_code")
    db["esp_licenses"][LICENSE_ID].pop("mqtt_password")
    new_id = "SLH-LIC-123456ABCDEF"
    db["esp_licenses"][new_id] = {
        "license_id": new_id, "device_id": DEVICE_ID, "owner_id": OWNER_UID, "status": "sold"
    }
    devices["devices"][DEVICE_ID]["license_key"] = new_id

    with patch("core.esp_license._load_json", side_effect=[devices, db]):
        result = esp_license.get_license(DEVICE_ID)

    assert result["license_id"] == new_id

def test_owner_command_requires_private_chat_and_never_replies_with_secrets():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from handlers.esp_handler import register_esp_handler

    bot = Mock()
    handlers = {}

    def decorator(**kwargs):
        def register(callback):
            for command in kwargs.get("commands", []):
                handlers[command] = callback
            return callback
        return register

    bot.message_handler.side_effect = decorator
    message = SimpleNamespace(
        text=f"/esp_revoke_license {LICENSE_ID}",
        from_user=SimpleNamespace(id=int(OWNER_UID)),
        chat=SimpleNamespace(type="private"),
    )
    safe_result = {
        "status": "REVOKED",
        "device_id": DEVICE_ID,
        "license_id_suffix": LICENSE_ID[-6:],
        "secrets_removed": ["activation_code", "mqtt_password"],
        "purchase_records_scrubbed": 1,
    }

    with patch("handlers.esp_handler.is_owner", return_value=True), patch(
        "core.esp_license.revoke_license", return_value=safe_result
    ) as revoke:
        register_esp_handler(bot)
        handlers["esp_revoke_license"](message)

    revoke.assert_called_once_with(LICENSE_ID, actor_uid=OWNER_UID)
    reply = bot.reply_to.call_args.args[1]
    assert SECRET_PASSWORD not in reply
    assert SECRET_ACTIVATION not in reply
    assert "בוטל" in reply


def test_owner_command_refuses_non_private_chat():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from handlers.esp_handler import register_esp_handler

    bot = Mock()
    handlers = {}

    def decorator(**kwargs):
        def register(callback):
            for command in kwargs.get("commands", []):
                handlers[command] = callback
            return callback
        return register

    bot.message_handler.side_effect = decorator
    message = SimpleNamespace(
        text=f"/esp_revoke_license {LICENSE_ID}",
        from_user=SimpleNamespace(id=int(OWNER_UID)),
        chat=SimpleNamespace(type="supergroup"),
    )
    with patch("handlers.esp_handler.is_owner", return_value=True), patch(
        "core.esp_license.revoke_license"
    ) as revoke:
        register_esp_handler(bot)
        handlers["esp_revoke_license"](message)

    revoke.assert_not_called()
    assert "פרטי" in bot.reply_to.call_args.args[1]
