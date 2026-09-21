import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class AgentEconomyFactoryTests(unittest.TestCase):
    def setUp(self):
        self._backend = os.environ.get("SLH_AGENT_ECONOMY_BACKEND")
        self._url = os.environ.get("SLH_AGENT_ECONOMY_DATABASE_URL")

    def tearDown(self):
        if self._backend is None:
            os.environ.pop("SLH_AGENT_ECONOMY_BACKEND", None)
        else:
            os.environ["SLH_AGENT_ECONOMY_BACKEND"] = self._backend
        if self._url is None:
            os.environ.pop("SLH_AGENT_ECONOMY_DATABASE_URL", None)
        else:
            os.environ["SLH_AGENT_ECONOMY_DATABASE_URL"] = self._url

    def test_file_backend_remains_available_for_local_tests(self):
        from slh_mcp.agent_economy_factory import get_agent_economy_service

        os.environ["SLH_AGENT_ECONOMY_BACKEND"] = "file"
        with tempfile.TemporaryDirectory() as tmp:
            service = get_agent_economy_service(root=Path(tmp))
        self.assertEqual(type(service).__name__, "AgentEconomyService")

    def test_postgres_backend_requires_database_url(self):
        from slh_mcp.agent_economy_factory import get_agent_economy_service

        os.environ["SLH_AGENT_ECONOMY_BACKEND"] = "postgres"
        os.environ.pop("SLH_AGENT_ECONOMY_DATABASE_URL", None)
        with self.assertRaises(ValueError):
            get_agent_economy_service()

    def test_postgres_backend_uses_configured_url(self):
        from slh_mcp.agent_economy_factory import get_agent_economy_service

        os.environ["SLH_AGENT_ECONOMY_BACKEND"] = "postgres"
        os.environ["SLH_AGENT_ECONOMY_DATABASE_URL"] = "postgresql://redacted@localhost/agent_economy"
        with patch(
            "slh_mcp.agent_economy_factory.PostgresAgentEconomyService"
        ) as service_cls:
            instance = object()
            service_cls.return_value = instance
            result = get_agent_economy_service()
        service_cls.assert_called_once_with("postgresql://redacted@localhost/agent_economy")
        self.assertIs(result, instance)


if __name__ == "__main__":
    unittest.main()
