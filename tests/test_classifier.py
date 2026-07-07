from skillbridge.classifier import (
    CLAUDE_ONLY,
    FULL,
    PARTIAL,
    classify,
    classify_by_rules,
)
from skillbridge.parser import parse_skill_folder


def test_pure_method_skill_is_full(fixture_skill):
    skill = parse_skill_folder(fixture_skill("pkm-processor"))
    result = classify_by_rules(skill)
    assert result.verdict == FULL
    assert result.claude_only_items == []
    assert "pkm-processor" in result.reasoning


def test_method_plus_execution_is_partial(fixture_skill):
    skill = parse_skill_folder(fixture_skill("deck-studio"))
    result = classify_by_rules(skill)
    assert result.verdict == PARTIAL
    # PRD acceptance 2: the pptx build is explicitly listed as Claude-only.
    assert any("pptx" in item.lower() or "scripts" in item.lower()
               for item in result.claude_only_items)


def test_execution_only_is_claude_only(fixture_skill):
    skill = parse_skill_folder(fixture_skill("pptx-toolkit"))
    result = classify_by_rules(skill)
    assert result.verdict == CLAUDE_ONLY


def test_llm_confirmation_pass_runs_in_mock_mode(fixture_skill):
    skill = parse_skill_folder(fixture_skill("pkm-processor"))
    result = classify(skill)
    assert result.verdict == FULL
    assert result.llm_note  # the confirmation pass recorded something


def test_rules_work_with_llm_totally_absent(fixture_skill, monkeypatch):
    # PRD F5: the rule layer must work with the LLM mocked/unavailable.
    import skillbridge.classifier as c

    class Dead:
        def generate(self, *a, **k):
            raise RuntimeError("no model")

    monkeypatch.setattr(c, "get_llm", lambda: Dead())
    skill = parse_skill_folder(fixture_skill("deck-studio"))
    result = c.classify(skill)
    assert result.verdict == PARTIAL
    assert "skipped" in result.llm_note
