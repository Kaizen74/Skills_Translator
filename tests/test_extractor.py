from skillbridge.classifier import classify_by_rules
from skillbridge.extractor import draft_method_core, extract_method_core
from skillbridge.parser import parse_skill_folder


def _core(fixture_skill, name):
    skill = parse_skill_folder(fixture_skill(name))
    return skill, extract_method_core(skill, classify_by_rules(skill))


def test_core_extracts_steps_and_purpose(fixture_skill):
    _, core = _core(fixture_skill, "pkm-processor")
    assert core["name"] == "pkm-processor"
    assert len(core["steps"]) == 5
    assert "inbox note" in core["purpose"].lower()
    assert core["trigger"] == "process"
    assert "escalate" in core["escalation"].lower()


def test_core_preserves_human_only_fields(fixture_skill):
    _, core = _core(fixture_skill, "pkm-processor")
    assert core["human_only_fields"] == ["IMPLICATION FOR PORTFOLIO"]


def test_core_examples_only_from_source(fixture_skill):
    _, core = _core(fixture_skill, "pkm-processor")
    assert len(core["examples"]) == 1
    assert "vertical AI agents" in core["examples"][0]
    # deck-studio has no Example section -> no examples may be invented (F8)
    _, core2 = _core(fixture_skill, "deck-studio")
    assert core2["examples"] == []


def test_core_lists_claude_only_items_for_partial(fixture_skill):
    _, core = _core(fixture_skill, "deck-studio")
    assert core["claude_only_items"]
    assert "escalate" in core["escalation"].lower()


def test_llm_refinement_cannot_alter_protected_fields(fixture_skill, monkeypatch):
    import skillbridge.extractor as ex

    class Malicious:
        def generate(self, prompt, system="", as_json=False):
            # A model that tries to invent examples and fill the human field.
            return (
                '{"purpose": "better wording", "examples": ["fabricated"], '
                '"human_only_fields": [], "name": "hacked"}'
            )

    monkeypatch.setattr(ex, "get_llm", lambda: Malicious())
    skill = parse_skill_folder(fixture_skill("pkm-processor"))
    draft = draft_method_core(skill, classify_by_rules(skill))
    core = ex.refine_with_llm(skill, draft)
    assert core["name"] == "pkm-processor"
    assert core["human_only_fields"] == ["IMPLICATION FOR PORTFOLIO"]
    assert core["examples"] == draft["examples"]  # source examples kept, nothing invented
    assert core["purpose"] == "better wording"  # benign refinement is accepted
