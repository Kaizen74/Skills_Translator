from skillbridge.classifier import classify_by_rules
from skillbridge.extractor import extract_method_core
from skillbridge.parser import parse_skill_folder
from skillbridge.translators import KINDS, generate_artefact, render
from skillbridge.validators import HERMES_MAX_CHARS, validate


def _core(fixture_skill, name):
    skill = parse_skill_folder(fixture_skill(name))
    cls = classify_by_rules(skill)
    return extract_method_core(skill, cls), cls


def test_hermes_rule_shape(fixture_skill):
    core, _ = _core(fixture_skill, "pkm-processor")
    text = render("hermes", core)
    assert text.startswith("Standing rule — 'process'")
    assert len(text) <= HERMES_MAX_CHARS
    assert "reply with" in text
    assert validate("hermes", text, core) == []


def test_hermes_length_cap_with_long_method(fixture_skill):
    core, _ = _core(fixture_skill, "pkm-processor")
    core["steps"] = [f"step {i} " + "detail " * 30 for i in range(12)]
    text = render("hermes", core)
    assert len(text) <= HERMES_MAX_CHARS
    assert validate("hermes", text, core) == []


def test_obsidian_template_shape(fixture_skill):
    core, cls = _core(fixture_skill, "pkm-processor")
    text = render("obsidian", core, version=1, portability=cls.verdict)
    assert text.startswith("---\nskill_source: pkm-processor")
    assert "portability: FULL" in text
    assert "## Method" in text and "- [ ]" in text
    assert "[[ ]]" in text  # wikilink-friendly
    assert validate("obsidian", text, core) == []


def test_promptpack_shape(fixture_skill):
    core, cls = _core(fixture_skill, "pkm-processor")
    text = render("promptpack", core, portability=cls.verdict)
    assert "## System prompt" in text
    assert "## User prompt scaffold" in text
    assert "## When to escalate to Claude" in text
    # F8: examples come from the source skill only
    assert "## Few-shot examples" in text
    assert "vertical AI agents" in text
    assert validate("promptpack", text, core) == []


def test_promptpack_no_examples_section_when_source_has_none(fixture_skill):
    core, cls = _core(fixture_skill, "deck-studio")
    text = render("promptpack", core, portability=cls.verdict)
    assert "## Few-shot examples" not in text


def test_partial_skill_artefacts_carry_escalation(fixture_skill):
    core, cls = _core(fixture_skill, "deck-studio")
    text = render("promptpack", core, portability=cls.verdict)
    assert "escalate" in text.lower()
    assert cls.verdict == "PARTIAL"


def test_generate_artefact_all_kinds_valid_in_mock_mode(fixture_skill):
    for name in ("pkm-processor", "deck-studio"):
        core, cls = _core(fixture_skill, name)
        for kind in KINDS:
            text, note = generate_artefact(kind, core, portability=cls.verdict)
            assert validate(kind, text, core) == [], f"{name}/{kind}: {validate(kind, text, core)}"
            assert note


def test_regenerate_with_steering_still_valid(fixture_skill):
    core, cls = _core(fixture_skill, "pkm-processor")
    text, note = generate_artefact(
        "hermes", core, portability=cls.verdict, steering="make it shorter"
    )
    assert validate("hermes", text, core) == []


def test_invalid_model_output_falls_back_to_safe_draft(fixture_skill, monkeypatch):
    import skillbridge.translators as tr

    class Bad:
        def generate(self, prompt, system="", as_json=False):
            return "x" * 2000  # violates every validator

    monkeypatch.setattr(tr, "get_llm", lambda: Bad())
    core, cls = _core(fixture_skill, "pkm-processor")
    for kind in KINDS:
        text, note = generate_artefact(kind, core, portability=cls.verdict)
        assert validate(kind, text, core) == []
        assert "deterministic" in note
