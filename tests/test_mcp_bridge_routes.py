import os
import unittest
from unittest.mock import patch

from flask import Flask


class MCPBridgeRouteTests(unittest.TestCase):
    def setUp(self):
        from core.mcp_bridge_routes import register_mcp_bridge_routes

        self.app = Flask(__name__)
        register_mcp_bridge_routes(self.app)
        self.client = self.app.test_client()

        self.env = {
            "SLH_MCP_BRIDGE_TOKEN": os.environ.get("SLH_MCP_BRIDGE_TOKEN"),
            "SLH_MCP_BRIDGE_PRINCIPAL_ID": os.environ.get("SLH_MCP_BRIDGE_PRINCIPAL_ID"),
            "SLH_MCP_PRINCIPAL_ID": os.environ.get("SLH_MCP_PRINCIPAL_ID"),
            "WHATSAPP_STORE_ENABLED": os.environ.get("WHATSAPP_STORE_ENABLED"),
            "SLH_WHATSAPP_STORE_BRIDGE_TOKEN": os.environ.get("SLH_WHATSAPP_STORE_BRIDGE_TOKEN"),
            "SLH_WHATSAPP_STORE_PRINCIPAL_ID": os.environ.get("SLH_WHATSAPP_STORE_PRINCIPAL_ID"),
        }
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "bridge-test"
        os.environ["SLH_MCP_BRIDGE_PRINCIPAL_ID"] = "owner"
        os.environ.pop("WHATSAPP_STORE_ENABLED", None)
        os.environ.pop("SLH_WHATSAPP_STORE_BRIDGE_TOKEN", None)
        os.environ.pop("SLH_WHATSAPP_STORE_PRINCIPAL_ID", None)

    def tearDown(self):
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_auth_is_rejected(self):
        response = self.client.get("/internal/mcp/v1/agents")
        self.assertEqual(response.status_code, 401)

    def test_client_cannot_override_configured_principal(self):
        source = {
            "1": {"id":"1","name":"A","owner_id":"owner","state":"idle"},
        }
        with patch(
            "core.mcp_bridge_routes.list_agents", return_value=source
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value=source,
        ) as visible, patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.get(
                "/internal/mcp/v1/agents",
                headers={
                    "Authorization": "Bearer bridge-test",
                    "X-SLH-MCP-Subject": "attacker",
                },
            )

        self.assertEqual(response.status_code, 200)
        visible.assert_called_once_with("owner", source)

    def test_agents_uses_canonical_visibility(self):
        source = {
            "1": {"id":"1","name":"A","owner_id":"owner","state":"idle","inbox":["secret"]},
            "2": {"id":"2","name":"B","owner_id":"other","state":"idle"},
        }
        with patch(
            "core.mcp_bridge_routes.list_agents", return_value=source
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value={"1": source["1"]},
        ) as visible, patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.get(
                "/internal/mcp/v1/agents",
                headers={"Authorization": "Bearer bridge-test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("inbox", response.get_json()["agents"][0])
        visible.assert_called_once_with("owner", source)

    def test_agent_execute_requires_command(self):
        with patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ), patch(
            "core.mcp_bridge_routes.list_agents", return_value={
                "1": {"id":"1","name":"A","owner_id":"owner","state":"idle"}
            }
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value={"1": {"id":"1","name":"A","owner_id":"owner","state":"idle"}},
        ), patch(
            "core.mcp_bridge_routes.get_agent",
            return_value=("1", {"id":"1","name":"A","owner_id":"owner","state":"idle"}),
        ):
            response = self.client.post(
                "/internal/mcp/v1/agents/1/execute",
                json={},
                headers={"Authorization": "Bearer bridge-test"},
            )
        self.assertEqual(response.status_code, 400)


    def _store_env(self):
        return {
            "WHATSAPP_STORE_ENABLED": "1",
            "SLH_WHATSAPP_STORE_BRIDGE_TOKEN": "store-test",
            "SLH_WHATSAPP_STORE_PRINCIPAL_ID": "999999999999999999",
        }

    def _store_headers(self):
        return {"Authorization": "Bearer store-test"}

    def test_whatsapp_store_is_default_off(self):
        response = self.client.get("/internal/commerce/v1/whatsapp/catalog")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "WHATSAPP_STORE_DISABLED")

    def test_whatsapp_catalog_requires_separate_store_bearer(self):
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch("core.mcp_bridge_routes.has_permission", return_value=True):
            response = self.client.get("/internal/commerce/v1/whatsapp/catalog")
        self.assertEqual(response.status_code, 401)

    def test_whatsapp_catalog_returns_stars_and_credits_items_but_hides_tests(self):
        canonical_items = {
            "agent_os": {"name": "Agent OS", "price": 199, "price_stars": 199, "type": "plugin", "grant": {"plugin": "secret"}},
            "course_ethereum": {"name": "Ethereum course", "price": 0, "price_stars": 299, "stars_only": True, "type": "course"},
            "esp32_pro": {"name": "ESP32 Pro", "price": 888, "type": "hardware", "grant": {"hardware": "secret"}},
            "bill_100_ils": {"name": "Physical note", "price": 50, "type": "physical", "grant": {"physical": "secret"}},
            "test_bill": {"name": "Test bill", "price": 5, "type": "physical"},
            "course_hidden_stars": {"name": "Broken stars item", "price": 0, "stars_only": True, "type": "course"},
        }
        products = {
            "esp32_pro": {"inventory": 12},
            "bill_100_ils": {"inventory": 4},
            "u_123_test_product": {"type": "physical", "price": 10, "inventory": 2, "seller_uid": "123"},
            "u_123_real_product": {"type": "physical", "price": 11, "inventory": 3, "seller_uid": "123", "name": "Real listing"},
            "u_124_market_smoke": {"type": "physical", "price": 1, "inventory": 1, "seller_uid": "124"},
        }
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
            "store.engine.load_items", return_value=canonical_items
        ), patch(
            "store.stars_purchase_service.get_stars_items",
            return_value={"agent_os": 199, "course_ethereum": 299},
        ), patch("state_manager.load_db", return_value={"products": products}):
            response = self.client.get(
                "/internal/commerce/v1/whatsapp/catalog", headers=self._store_headers()
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["payment_in_whatsapp"])
        items = {item["sku"]: item for item in payload["items"]}
        self.assertEqual(set(items), {"agent_os", "course_ethereum", "esp32_pro", "bill_100_ils", "u_123_real_product"})
        self.assertEqual(items["agent_os"]["checkout_channel"], "telegram_stars")
        self.assertEqual(items["agent_os"]["checkout_command"], "/buystars agent_os")
        self.assertEqual(items["esp32_pro"]["checkout_channel"], "telegram_credits")
        self.assertEqual(items["esp32_pro"]["price"], 888)
        self.assertEqual(items["esp32_pro"]["stock_remaining"], 12)
        self.assertEqual(items["bill_100_ils"]["stock_remaining"], 4)
        self.assertEqual(items["u_123_real_product"]["checkout_command"], "/buy u_123_real_product")
        self.assertNotIn("grant", items["agent_os"])
        self.assertNotIn("seller_uid", items["u_123_real_product"])
        self.assertNotIn("test_bill", items)
        self.assertNotIn("u_123_test_product", items)
        self.assertNotIn("u_124_market_smoke", items)
        self.assertNotIn("course_hidden_stars", items)

    def test_whatsapp_store_rejects_owner_wildcard_role(self):
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="OWNER"
        ), patch("core.mcp_bridge_routes.has_permission", return_value=True):
            response = self.client.get(
                "/internal/commerce/v1/whatsapp/catalog", headers=self._store_headers()
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "WHATSAPP_STORE_PRINCIPAL_ROLE_REQUIRED")

    def test_whatsapp_credit_inquiry_is_idempotent_and_nonfinancial(self):
        db = {}
        def atomic_update(mutate):
            return mutate(db)
        canonical_items = {"esp32_pro": {"name": "ESP32 Pro", "price": 888, "type": "hardware"}}
        products = {"esp32_pro": {"inventory": 12}}
        payload = {
            "provider": "twilio",
            "provider_message_id": "SM1234567890abcdef",
            "sku": "esp32_pro",
            "intent": "purchase_inquiry",
            "customer_confirmed": True,
        }
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
            "store.engine.load_items", return_value=canonical_items
        ), patch("store.stars_purchase_service.get_stars_items", return_value={}), patch(
            "state_manager.load_db", return_value={"products": products}
        ), patch("state_manager.atomic_update", side_effect=atomic_update):
            first = self.client.post(
                "/internal/commerce/v1/whatsapp/intents", json=payload, headers=self._store_headers()
            )
            second = self.client.post(
                "/internal/commerce/v1/whatsapp/intents", json=payload, headers=self._store_headers()
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.get_json()["duplicate"])
        self.assertTrue(second.get_json()["duplicate"])
        self.assertEqual(first.get_json()["currency"], "Credits")
        self.assertEqual(first.get_json()["checkout_command"], "/buy esp32_pro")
        self.assertFalse(first.get_json()["financial_mutation"])
        self.assertFalse(first.get_json()["payment_in_whatsapp"])
        self.assertEqual(len(db["whatsapp_purchase_intents"]), 1)
        self.assertNotIn("provider_message_id", next(iter(db["whatsapp_purchase_intents"].values())))

    def test_whatsapp_intent_replay_with_changed_sku_conflicts(self):
        db = {}
        def atomic_update(mutate):
            return mutate(db)
        items = {
            "agent_os": {"name": "Agent OS", "price": 199, "price_stars": 199, "type": "plugin"},
            "course_ethereum": {"name": "Ethereum", "price": 0, "price_stars": 299, "stars_only": True, "type": "course"},
        }
        payload = {
            "provider": "twilio",
            "provider_message_id": "SM1234567890abcdef",
            "sku": "agent_os",
            "intent": "purchase_inquiry",
            "customer_confirmed": True,
        }
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
            "store.engine.load_items", return_value=items
        ), patch("store.stars_purchase_service.get_stars_items", return_value={"agent_os": 199, "course_ethereum": 299}), patch(
            "state_manager.load_db", return_value={"products": {}}
        ), patch("state_manager.atomic_update", side_effect=atomic_update):
            first = self.client.post(
                "/internal/commerce/v1/whatsapp/intents", json=payload, headers=self._store_headers()
            )
            conflict = self.client.post(
                "/internal/commerce/v1/whatsapp/intents",
                json={**payload, "sku": "course_ethereum"},
                headers=self._store_headers(),
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(len(db["whatsapp_purchase_intents"]), 1)

    def test_whatsapp_intent_requires_explicit_confirmation(self):
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch("core.mcp_bridge_routes.has_permission", return_value=True):
            response = self.client.post(
                "/internal/commerce/v1/whatsapp/intents",
                json={
                    "provider": "twilio",
                    "provider_message_id": "SM1234567890abcdef",
                    "sku": "agent_os",
                    "intent": "purchase_inquiry",
                    "customer_confirmed": False,
                },
                headers=self._store_headers(),
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "EXPLICIT_PURCHASE_INQUIRY_REQUIRED")

    def test_whatsapp_store_service_role_is_scoped(self):
        from core.authority import get_role, has_permission
        service_id = "999999999999999999"
        with patch("core.authority.WHATSAPP_STORE_SERVICE_IDS", {service_id}):
            self.assertEqual(get_role(service_id), "WHATSAPP_STORE_SERVICE")
            self.assertTrue(has_permission(service_id, "whatsapp.store"))
            self.assertFalse(has_permission(service_id, "exec.audit"))
            self.assertFalse(has_permission(service_id, "agents.manage"))


if __name__ == "__main__":
    unittest.main()