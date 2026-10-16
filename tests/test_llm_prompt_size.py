from handlers import llm_handler


def test_compact_prompt_preserves_edges():
    prompt = "SYSTEM" + ("x" * 12000) + "USER QUESTION"
    compact = llm_handler._compact_prompt(prompt, max_chars=5000)
    assert len(compact) <= 5000
    assert compact.startswith("SYSTEM")
    assert "USER QUESTION" in compact
    assert "CONTEXT COMPACTED" in compact


def test_short_prompt_is_unchanged():
    prompt = "hello"
    assert llm_handler._compact_prompt(prompt, max_chars=5000) == prompt


def test_slh_system_rules_prevent_repetitive_progress_updates():
    assert "AUTONOMOUS UPDATE POLICY" in llm_handler.SLH_SYSTEM_RULES
    assert "Never suggest an unimplemented command as if it exists" in llm_handler.SLH_SYSTEM_RULES
