from core.runtime_command_evidence import snapshot_bot


class FakeBot:
    def __init__(self):
        def first(message):
            pass

        def second(message):
            pass

        def third(message):
            pass

        first.__module__ = "handlers.first"
        first.__qualname__ = "register.<locals>.first"
        second.__module__ = "handlers.second"
        second.__qualname__ = "register.<locals>.second"
        third.__module__ = "handlers.third"
        third.__qualname__ = "register.<locals>.third"

        self.message_handlers = [
            {"filters": {"commands": ["alpha", "shared"]}, "function": first},
            {"filters": {"commands": ["shared"]}, "function": second},
            {"filters": {"commands": ["beta"]}, "function": third},
            {"filters": {"content_types": ["text"]}, "function": third},
        ]


def test_snapshot_reads_live_message_handlers_without_dispatching():
    result = snapshot_bot("test", FakeBot())

    assert result["source"] == "TeleBot.message_handlers"
    assert result["total_message_handlers"] == 4
    assert result["unique_commands"] == 3
    assert result["command_registrations"] == 4
    assert [item["registration_index"] for item in result["collisions"]["/shared"]] == [0, 1]
    assert result["commands"]["/alpha"][0]["module"] == "handlers.first"
    assert result["commands"]["/beta"][0]["function"] == "third"
