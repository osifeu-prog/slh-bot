import os
import unittest
from unittest.mock import patch

from core import railway_control


class RailwayExchangeGateControlTests(unittest.TestCase):
    def test_status_returns_only_exchange_flag_not_other_variables(self):
        with patch.object(
            railway_control,
            "graphql",
            return_value={
                "variables": {
                    "SLH_EXCHANGE_PUBLIC_OPEN": "1",
                    "BOT_TOKEN": "must-not-be-returned",
                }
            },
        ) as graphql:
            status = railway_control.exchange_gate_variable_status()

        self.assertEqual(status["configured"], "1")
        self.assertTrue(status["configured_open"])
        self.assertEqual(status["source"], "railway_service_production")
        self.assertNotIn("BOT_TOKEN", str(status))
        self.assertNotIn("must-not-be-returned", str(status))
        self.assertEqual(
            graphql.call_args.args[1],
            {
                "projectId": railway_control.SLH_BOT_PROJECT_ID,
                "environmentId": railway_control.SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
                "serviceId": railway_control.SLH_BOT_SERVICE_ID,
            },
        )

    def test_close_updates_only_gate_variable_then_deploys_same_runtime_commit(self):
        commit = "a" * 40
        responses = [
            {"variables": {"SLH_EXCHANGE_PUBLIC_OPEN": "1", "ANOTHER_SECRET": "redacted"}},
            {"variableUpsert": True},
            {"variables": {"SLH_EXCHANGE_PUBLIC_OPEN": "0", "ANOTHER_SECRET": "redacted"}},
        ]
        with patch.object(railway_control, "graphql", side_effect=responses) as graphql, \
             patch.dict(os.environ, {"RAILWAY_GIT_COMMIT_SHA": commit}, clear=False), \
             patch.object(railway_control, "deploy", return_value={"id": "dep-123"}) as deploy:
            result = railway_control.close_exchange_gate()

        self.assertEqual(result["status"], "DEPLOY_TRIGGERED")
        self.assertEqual(result["previous"], "1")
        self.assertEqual(result["configured"], "0")
        self.assertEqual(result["commit"], commit)
        self.assertEqual(result["deployment_id"], "dep-123")
        self.assertEqual(result["service"], "slh-cloud-bot")
        self.assertEqual(graphql.call_count, 3)

        mutation_query = graphql.call_args_list[1].args[0]
        mutation_vars = graphql.call_args_list[1].args[1]["input"]
        self.assertIn("variableUpsert", mutation_query)
        self.assertEqual(
            mutation_vars,
            {
                "projectId": railway_control.SLH_BOT_PROJECT_ID,
                "environmentId": railway_control.SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
                "serviceId": railway_control.SLH_BOT_SERVICE_ID,
                "name": "SLH_EXCHANGE_PUBLIC_OPEN",
                "value": "0",
                "skipDeploys": True,
            },
        )
        deploy.assert_called_once_with(
            railway_control.SLH_BOT_SERVICE_ID,
            railway_control.SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
            commit,
        )

    def test_close_does_not_deploy_if_railway_value_cannot_be_verified(self):
        responses = [
            {"variables": {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}},
            {"variableUpsert": True},
            {"variables": {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}},
        ]
        with patch.object(railway_control, "graphql", side_effect=responses), \
             patch.object(railway_control, "deploy") as deploy:
            with self.assertRaisesRegex(
                railway_control.RailwayControlError,
                "EXCHANGE_GATE_VARIABLE_VERIFY_FAILED",
            ):
                railway_control.close_exchange_gate()
        deploy.assert_not_called()



    def test_account_token_is_preferred_for_exchange_control_when_both_exist(self):
        with patch.dict(os.environ, {
            "RAILWAY_PROJECT_TOKEN": "project-token",
            "RAILWAY_API_TOKEN": "workspace-token",
        }, clear=False):
            headers = railway_control._auth_headers(prefer_account_token=True)
        self.assertEqual(headers.get("Authorization"), "Bearer workspace-token")
        self.assertNotIn("Project-Access-Token", headers)

    def test_safe_error_codes_never_echo_error_payload(self):
        cases = [
            ("Railway token is not configured", "RAILWAY_CONTROL_TOKEN_MISSING"),
            ("Railway API HTTP 401: secret body", "RAILWAY_AUTHENTICATION_FAILED"),
            ("Railway API HTTP 403: permission denied", "RAILWAY_ACCESS_DENIED"),
            ("Railway API connection failed: timeout", "RAILWAY_API_UNREACHABLE"),
        ]
        for message, expected in cases:
            actual = railway_control.safe_railway_error_code(RuntimeError(message))
            self.assertEqual(actual, expected)
            self.assertNotIn("secret body", actual)

if __name__ == "__main__":
    unittest.main()
