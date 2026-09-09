import unittest
from unittest.mock import patch

from core import mint_authority


OWNER_UID = "8789977826"
PARTNER_UID = "5010371391"


class MintAuthorityTests(unittest.TestCase):
    def test_partner_cannot_mint(self):
        with patch.object(mint_authority.economy_service, "record_transaction") as record:
            with self.assertRaises(PermissionError):
                mint_authority.mint_credits(PARTNER_UID, "123", 100, reason="test")
            record.assert_not_called()

    def test_unknown_user_cannot_mint(self):
        with patch.object(mint_authority.economy_service, "record_transaction") as record:
            with self.assertRaises(PermissionError):
                mint_authority.mint_credits("not-owner", "123", 100, reason="test")
            record.assert_not_called()

    def test_owner_can_mint(self):
        with patch.object(mint_authority.economy_service, "record_transaction", return_value=100) as record:
            result = mint_authority.mint_credits(
                OWNER_UID,
                "123",
                100,
                reason="airdrop",
                meta={"source": "test"},
            )

        self.assertEqual(result, 100)
        record.assert_called_once()
        args, kwargs = record.call_args
        self.assertEqual(args[0], "123")
        self.assertEqual(args[1], 100)
        self.assertEqual(kwargs["reason"], "airdrop")
        self.assertEqual(kwargs["meta"]["issuer_uid"], OWNER_UID)
        self.assertEqual(kwargs["meta"]["source"], "mint_authority")
        self.assertEqual(kwargs["meta"]["permission"], "economy.mint")


if __name__ == "__main__":
    unittest.main()
