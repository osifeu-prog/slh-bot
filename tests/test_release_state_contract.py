import json
import os
import unittest
from unittest.mock import patch

from core.control_center import get_full_system_map, get_release_state


class TestReleaseStateContract(unittest.TestCase):
    def _base_patches(self):
        return [
            patch("core.system_check.run_system_checks", return_value={"status": "PASS"}),
            patch("core.alpha_control_plane.evaluate", return_value={"status": "READY", "system_status": "READY"}),
            patch("core.alpha_control_plane.alpha_state", return_value={"status": "CLOSED"}),
            patch("core.bnb_gate.bnb_readiness", return_value={"effective_open": False}),
            patch("core.ton_deposit_service.deposits_are_open", return_value=False),
            patch("core.control_center._load_registry", return_value={"schema_version": "test", "railway_projects": []}),
        ]

    def test_release_state_is_read_only_and_structured(self):
        patches = self._base_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5],              patch.dict(os.environ, {}, clear=True):
            state = get_release_state()

        self.assertEqual(state["scope"], "read_only")
        self.assertEqual(state["overall"], "DEGRADED")
        self.assertIn("evidence", state)
        self.assertIn("next_actions", state)
        self.assertIn("tests", state["readiness"])
        self.assertIn("ci", state["readiness"])
        self.assertIn("e2e", state["readiness"])
        self.assertEqual(state["readiness"]["runtime"], "READY")
        self.assertEqual(state["readiness"]["alpha"], "READY")
        self.assertEqual(state["current_state"]["alpha"], "CLOSED")
        self.assertEqual(state["current_state"]["bnb_settlement"], "CLOSED")
        self.assertEqual(state["current_state"]["ton_settlement"], "CLOSED")
        self.assertEqual(state["release_evidence"]["matching_sha"], False)
        self.assertIsInstance(state["auto_actions"], list)
        self.assertIsInstance(state["owner_actions"], list)
        self.assertIsInstance(state["next_actions"], list)

    def test_matching_evidence_promotes_only_verified_dimensions(self):
        sha = "abc123"
        evidence = {
            "sha": sha,
            "ci": {
                "status": "PASS",
                "code_validated": True,
                "tests_passed": True,
            },
            "deployment": {"status": "SUCCESS"},
        }
        with patch.dict(os.environ, {
            "RAILWAY_GIT_COMMIT_SHA": sha,
            "SLH_RELEASE_EVIDENCE_JSON": json.dumps(evidence),
        }, clear=True),              patch("core.system_check.run_system_checks", return_value={"status": "PASS"}),              patch("core.alpha_control_plane.evaluate", return_value={"status": "READY"}),              patch("core.alpha_control_plane.alpha_state", return_value={"status": "CLOSED"}),              patch("core.bnb_gate.bnb_readiness", return_value={"effective_open": False}),              patch("core.ton_deposit_service.deposits_are_open", return_value=False),              patch("core.control_center._load_registry", return_value={"schema_version": "test", "railway_projects": []}):
            state = get_release_state()

        self.assertEqual(state["release_evidence"]["status"], "MATCHED")
        self.assertTrue(state["release_evidence"]["matching_sha"])
        self.assertEqual(state["readiness"]["code"], "READY")
        self.assertEqual(state["readiness"]["tests"], "READY")
        self.assertEqual(state["readiness"]["ci"], "READY")
        self.assertEqual(state["readiness"]["deployment"], "UNKNOWN")
        self.assertEqual(state["deployment_verification"], "UNVERIFIED")
        self.assertEqual(state["deployment_identity"]["status"], "IDENTIFIED")
        self.assertNotIn("release_evidence_sha_mismatch", state["warnings"])

    def test_github_handoff_never_counts_as_deployment_verification(self):
        sha = "abc123"
        evidence = {
            "sha": sha,
            "ci": {"status": "PASS", "code_validated": True, "tests_passed": True},
            "deployment": {"status": "SUCCESS", "source": "github_handoff"},
        }
        with patch.dict(os.environ, {
            "RAILWAY_GIT_COMMIT_SHA": sha,
            "SLH_RELEASE_EVIDENCE_JSON": json.dumps(evidence),
        }, clear=True),              patch("core.system_check.run_system_checks", return_value={"status": "PASS"}),              patch("core.alpha_control_plane.evaluate", return_value={"status": "READY"}),              patch("core.alpha_control_plane.alpha_state", return_value={"status": "CLOSED"}),              patch("core.bnb_gate.bnb_readiness", return_value={"effective_open": False}),              patch("core.ton_deposit_service.deposits_are_open", return_value=False),              patch("core.control_center._load_registry", return_value={"schema_version": "test", "railway_projects": []}):
            state = get_release_state()

        self.assertEqual(state["readiness"]["deployment"], "UNKNOWN")
        self.assertEqual(state["deployment_verification"], "UNVERIFIED")

    def test_railway_runtime_source_can_verify_matching_deployment(self):
        sha = "abc123"
        evidence = {
            "sha": sha,
            "ci": {"status": "PASS", "code_validated": True, "tests_passed": True},
            "deployment": {"status": "SUCCESS", "source": "railway_runtime"},
        }
        with patch.dict(os.environ, {
            "RAILWAY_GIT_COMMIT_SHA": sha,
            "SLH_RELEASE_EVIDENCE_JSON": json.dumps(evidence),
        }, clear=True),              patch("core.system_check.run_system_checks", return_value={"status": "PASS"}),              patch("core.alpha_control_plane.evaluate", return_value={"status": "READY"}),              patch("core.alpha_control_plane.alpha_state", return_value={"status": "CLOSED"}),              patch("core.bnb_gate.bnb_readiness", return_value={"effective_open": False}),              patch("core.ton_deposit_service.deposits_are_open", return_value=False),              patch("core.control_center._load_registry", return_value={"schema_version": "test", "railway_projects": []}):
            state = get_release_state()

        self.assertEqual(state["readiness"]["deployment"], "READY")
        self.assertEqual(state["deployment_verification"], "railway_runtime")
    def test_mismatched_evidence_never_counts_as_pass(self):
        evidence = {
            "sha": "old-sha",
            "ci": {"status": "PASS", "code_validated": True, "tests_passed": True},
            "deployment": {"status": "SUCCESS"},
        }
        with patch.dict(os.environ, {
            "RAILWAY_GIT_COMMIT_SHA": "current-sha",
            "SLH_RELEASE_EVIDENCE_JSON": json.dumps(evidence),
        }, clear=True),              patch("core.system_check.run_system_checks", return_value={"status": "PASS"}),              patch("core.alpha_control_plane.evaluate", return_value={"status": "READY"}),              patch("core.alpha_control_plane.alpha_state", return_value={"status": "CLOSED"}),              patch("core.bnb_gate.bnb_readiness", return_value={"effective_open": False}),              patch("core.ton_deposit_service.deposits_are_open", return_value=False),              patch("core.control_center._load_registry", return_value={"schema_version": "test", "railway_projects": []}):
            state = get_release_state()

        self.assertEqual(state["release_evidence"]["status"], "STALE")
        self.assertFalse(state["release_evidence"]["matching_sha"])
        self.assertEqual(state["readiness"]["code"], "UNKNOWN")
        self.assertEqual(state["deployment_verification"], "UNVERIFIED")
        self.assertEqual(state["deployment_identity"]["status"], "IDENTIFIED")
        self.assertEqual(state["readiness"]["tests"], "UNKNOWN")
        self.assertEqual(state["readiness"]["ci"], "UNKNOWN")
        self.assertIn("release_evidence_sha_mismatch", state["warnings"])

    def test_release_state_is_exposed_through_system_map(self):
        with patch("core.system_check.run_system_checks", return_value={"status": "PASS"}),              patch("core.alpha_control_plane.evaluate", return_value={"status": "READY", "system_status": "READY"}),              patch("core.alpha_control_plane.alpha_state", return_value={"status": "CLOSED"}),              patch("core.bnb_gate.bnb_readiness", return_value={"effective_open": False}),              patch("core.ton_deposit_service.deposits_are_open", return_value=False),              patch("core.control_center._load_registry", return_value={"schema_version": "test", "railway_projects": []}),              patch.dict(os.environ, {}, clear=True):
            system_map = get_full_system_map()

        self.assertIn("release_state", system_map)
        self.assertEqual(system_map["release_state"]["scope"], "read_only")
        self.assertEqual(system_map["release_state"]["current_state"]["bnb_settlement"], "CLOSED")
        self.assertEqual(system_map["release_state"]["current_state"]["ton_settlement"], "CLOSED")


if __name__ == "__main__":
    unittest.main()
