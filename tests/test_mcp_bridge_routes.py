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
        os.environ["WHATSAPP_STORE_ENABLED"] = "0"
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

    def test_whatsapp_store_is_disabled_by_default(self):
        response = self.client.get("/internal/commerce/v1/whatsapp/catalog")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "WHATSAPP_STORE_DISABLED")

    def test_whatsapp_catalog_requires_dedicated_bearer(self):
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.get("/internal/commerce/v1/whatsapp/catalog")
        self.assertEqual(response.status_code, 401)

    def test_whatsapp_catalog_returns_only_canonical_stars_items(self):
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ), patch(
            "store.engine.load_items",
            return_value={
                "agent_os": {"name": "Agent OS", "description": "Approved digital product", "grant": {"plugin": "secret"}},
                "free_item": {"name": "Free item", "price_stars": 0},
            },
        ), patch(
            "store.stars_purchase_service.get_stars_items",
            return_value={"agent_os": 199},
        ):
            response = self.client.get(
                "/internal/commerce/v1/whatsapp/catalog",
                headers={"Authorization": "Bearer store-test"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["currency"], "XTR")
        self.assertFalse(payload["payment_in_whatsapp"])
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["sku"], "agent_os")
        self.assertEqual(item["price"], 199)
        self.assertEqual(item["checkout_channel"], "telegram_stars")
        self.assertNotIn("grant", item)
        self.assertNotIn("owner_id", item)

    def test_whatsapp_purchase_inquiry_is_idempotent_and_nonfinancial(self):
        db = {}
        def atomic_update(mutate):
            return mutate(db)

        payload = {
            "provider": "twilio",
            "provider_message_id": "SM1234567890abcdef",
            "sku": "agent_os",
            "intent": "purchase_inquiry",
            "customer_confirmed": True,
        }
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ), patch(
            "store.engine.load_items",
            return_value={"agent_os": {"name": "Agent OS", "price_stars": 199}},
        ), patch(
            "store.stars_purchase_service.get_stars_items",
            return_value={"agent_os": 199},
        ), patch(
            "state_manager.atomic_update", side_effect=atomic_update
        ):
            first = self.client.post(
                "/internal/commerce/v1/whatsapp/intents",
                json=payload,
                headers={"Authorization": "Bearer store-test"},
            )
            second = self.client.post(
                "/internal/commerce/v1/whatsapp/intents",
                json=payload,
                headers={"Authorization": "Bearer store-test"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.get_json()["duplicate"])
        self.assertTrue(second.get_json()["duplicate"])
        self.assertEqual(first.get_json()["intent_id"], second.get_json()["intent_id"])
        self.assertEqual(first.get_json()["status"], "inquiry_pending")
        self.assertFalse(first.get_json()["financial_mutation"])
        self.assertEqual(len(db["whatsapp_purchase_intents"]), 1)
        row = next(iter(db["whatsapp_purchase_intents"].values()))
        self.assertNotIn("provider_message_id", row)
        self.assertEqual(set(db.keys()), {"whatsapp_purchase_intents"})

    def test_whatsapp_purchase_inquiry_rejects_replayed_message_with_changed_sku(self):
        db = {}
        def atomic_update(mutate):
            return mutate(db)

        base = {
            "provider": "twilio",
            "provider_message_id": "SM1234567890abcdef",
            "sku": "agent_os",
            "intent": "purchase_inquiry",
            "customer_confirmed": True,
        }
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ), patch(
            "store.engine.load_items",
            return_value={
                "agent_os": {"name": "Agent OS"},
                "course_algo_trading": {"name": "Algorithmic Trading"},
            },
        ), patch(
            "store.stars_purchase_service.get_stars_items",
            return_value={"agent_os": 199, "course_algo_trading": 150},
        ), patch(
            "state_manager.atomic_update", side_effect=atomic_update
        ):
            first = self.client.post(
                "/internal/commerce/v1/whatsapp/intents",
                json=base,
                headers={"Authorization": "Bearer store-test"},
            )
            conflict = self.client.post(
                "/internal/commerce/v1/whatsapp/intents",
                json={**base, "sku": "course_algo_trading"},
                headers={"Authorization": "Bearer store-test"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(len(db["whatsapp_purchase_intents"]), 1)

    def test_whatsapp_purchase_inquiry_requires_explicit_customer_confirmation(self):
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="WHATSAPP_STORE_SERVICE"
        ), patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.post(
                "/internal/commerce/v1/whatsapp/intents",
                json={
                    "provider": "twilio",
                    "provider_message_id": "SM1234567890abcdef",
                    "sku": "agent_os",
                    "intent": "purchase_inquiry",
                    "customer_confirmed": False,
                },
                headers={"Authorization": "Bearer store-test"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "EXPLICIT_PURCHASE_INQUIRY_REQUIRED")


    def test_whatsapp_store_rejects_owner_role_even_if_permission_wildcard_would_pass(self):
        with patch.dict(os.environ, self._store_env()), patch(
            "core.mcp_bridge_routes.get_role", return_value="OWNER"
        ), patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.get(
                "/internal/commerce/v1/whatsapp/catalog",
                headers={"Authorization": "Bearer store-test"},
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "WHATSAPP_STORE_PRINCIPAL_ROLE_REQUIRED")

    def test_canonical_whatsapp_service_role_has_only_store_permission(self):
        from core.authority import get_role, has_permission

        service_id = "999999999999999999"
        with patch("core.authority.WHATSAPP_STORE_SERVICE_IDS", {service_id}):
            self.assertEqual(get_role(service_id), "WHATSAPP_STORE_SERVICE")
            self.assertTrue(has_permission(service_id, "whatsapp.store"))
            self.assertFalse(has_permission(service_id, "exec.audit"))
            self.assertFalse(has_permission(service_id, "agents.manage"))


if __name__ == "__main__":
    unittest.main()