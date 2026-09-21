                "test",
            )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.economy.balance("1"), 15)
        self.assertEqual(self.economy.balance("2"), 5)

    def test_mission_completion_uses_canonical_lifecycle(self):
        from core.control_plane_api import mission_complete_control

        fake = type(
            "FakeLifecycle",
            (),
            {
                "complete_mission": lambda self, mission_id: {
                    "status": "completed",
                    "mission_id": mission_id,
                }
            },
        )
        with patch("core.control_plane_api.MissionLifecycleService", fake):
            result = mission_complete_control(str(OWNER_TELEGRAM_ID), "m1")
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()