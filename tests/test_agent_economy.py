        self.economy.record_revenue(
            amount=100, operation_id="revenue-1", actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue", evidence={"event_id": "external-1"},
        )
        self.economy.treasury_fund(
            agent_id="agent-1", amount=100, operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID), reason="bootstrap",
        )
        first = self.economy.transfer(
            source_agent="agent-1", target_agent="agent-2", amount=25,
            operation_id="transfer-1", actor=str(OWNER_TELEGRAM_ID), reason="work",
        )
        second = self.economy.transfer(
            source_agent="agent-1", target_agent="agent-2", amount=25,
            operation_id="transfer-1", actor=str(OWNER_TELEGRAM_ID), reason="work",
        )
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(self.economy.balance("agent-1"), 75)
        self.assertEqual(self.economy.balance("agent-2"), 25)
        self.assertEqual(len(self.economy.ledger()), 5)

    def test_insufficient_balance_is_rejected_atomically(self):
        with self.assertRaises(ValueError):
            self.economy.transfer(
                source_agent="agent-1", target_agent="agent-2", amount=1,
                operation_id="transfer-x", actor=str(OWNER_TELEGRAM_ID), reason="work",
            )
        self.assertEqual(self.economy.balance("agent-1"), 0)
        self.assertEqual(self.economy.balance("agent-2"), 0)
        self.assertEqual(self.economy.ledger(), [])

    def test_negative_and_zero_amounts_are_rejected(self):
        for amount in (0, -1):
            with self.assertRaises(ValueError):
                self.economy.record_revenue(