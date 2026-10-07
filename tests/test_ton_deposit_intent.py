import unittest
from unittest.mock import patch

from core import ton_deposit_service as service


OWNER="8789977826"
OWNER_RAW="0:37197c019cf55caf62c6c34293fc695c912845970c6ee56ad803d81c62eccdc3"
TREASURY="EQCd7XHWGj06cBLlWW_DZUN3TWMGr_oWoVy0G0LkC14gQhSm"


class TonDepositIntentTests(unittest.TestCase):
    def _tx(self, *, memo="SLH8789977826", utime=1000, amount="0.01"):
        return {
            "from": OWNER_RAW,
            "to": TREASURY,
            "amount_ton": amount,
            "memo": memo,
            "utime": utime,
        }

    def _db(self, *, status="pending", memo="SLH8789977826", created=1000, expires=2800):
        return {
            "ton_deposit_intents": {
                "intent-1": {
                    "uid": OWNER,
                    "status": status,
                    "amount_nano": "10000000",
                    "treasury": TREASURY,
                    "memo": memo,
                    "binding_address_raw": OWNER_RAW,
                    "created_at_epoch": created,
                    "expires_at_epoch": expires,
                }
            }
        }

    def test_matching_intent_is_audit_correlation_only(self):
        with patch.object(service.state_manager, "load_db", return_value=self._db()):
            self.assertEqual(
                service._match_deposit_intent(OWNER, self._tx()),
                "intent-1",
            )

    def test_missing_memo_does_not_match_intent(self):
        with patch.object(service.state_manager, "load_db", return_value=self._db()):
            self.assertIsNone(
                service._match_deposit_intent(
                    OWNER,
                    self._tx(memo=""),
                )
            )

    def test_expired_intent_does_not_match(self):
        with patch.object(
            service.state_manager,
            "load_db",
            return_value=self._db(created=100, expires=200),
        ):
            self.assertIsNone(
                service._match_deposit_intent(
                    OWNER,
                    self._tx(utime=1000),
                )
            )

    def test_specific_intent_id_is_scoped(self):
        with patch.object(service.state_manager, "load_db", return_value=self._db()):
            self.assertEqual(
                service._match_deposit_intent(
                    OWNER,
                    self._tx(),
                    intent_id="intent-1",
                ),
                "intent-1",
            )
            self.assertIsNone(
                service._match_deposit_intent(
                    OWNER,
                    self._tx(),
                    intent_id="other-intent",
                )
            )


if __name__ == "__main__":
    unittest.main()
