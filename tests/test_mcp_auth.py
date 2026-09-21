import unittest

from core.identity import OWNER_TELEGRAM_ID


class MCPAuthTests(unittest.TestCase):
    def test_missing_token_has_no_principal(self):
        from slh_mcp.auth import Principal
        self.assertIsNone(
            Principal.from_headers({}, "expected", "owner", None, ())
        )

    def test_wrong_token_has_no_principal(self):
        from slh_mcp.auth import Principal
        self.assertIsNone(
            Principal.from_headers(
                {"authorization": "Bearer wrong"},
                "expected",
                "owner",
                None,
                (),
            )
        )

    def test_valid_token_resolves_principal(self):
        from slh_mcp.auth import Principal
        principal = Principal.from_headers(
            {"Authorization": "Bearer expected"},
            "expected",
            str(OWNER_TELEGRAM_ID),
            None,
            (),
        )
        self.assertIsNotNone(principal)
        self.assertEqual(principal.subject, str(OWNER_TELEGRAM_ID))

    def test_owner_authorization_uses_canonical_authority(self):
        from slh_mcp.auth import Principal, authorize
        principal = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )
        self.assertTrue(authorize(principal, "exec.audit"))

    def test_unknown_principal_is_denied(self):
        from slh_mcp.auth import Principal, authorize
        principal = Principal(
            subject="1",
            role="UNKNOWN",
            permissions=frozenset(),
        )
        self.assertFalse(authorize(principal, "exec.audit"))

    def test_redaction_masks_bearer(self):
        from slh_mcp.auth import redact
        value = "Authorization: Bearer secret-value"
        result = redact(value)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("secret-value", result)


if __name__ == "__main__":
    unittest.main()
