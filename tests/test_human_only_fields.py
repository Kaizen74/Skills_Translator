"""PRD N2: a dedicated test that FAILS THE BUILD if any generated artefact
populates IMPLICATION FOR PORTFOLIO or Operator Decision.

This is the hard guarantee behind PRD principle 5 and acceptance criterion 3.
"""

import re

from skillbridge.classifier import classify_by_rules
from skillbridge.extractor import extract_method_core
from skillbridge.parser import HUMAN_ONLY_INSTRUCTION, parse_skill_folder
from skillbridge.translators import KINDS, generate_artefact
from skillbridge.validators import check_human_only_fields


def _all_artefacts(fixture_skill, name):
    skill = parse_skill_folder(fixture_skill(name))
    cls = classify_by_rules(skill)
    core = extract_method_core(skill, cls)
    return skill, core, {
        kind: generate_artefact(kind, core, portability=cls.verdict)[0] for kind in KINDS
    }


def test_every_artefact_keeps_implication_for_portfolio_blank(fixture_skill):
    skill, core, artefacts = _all_artefacts(fixture_skill, "pkm-processor")
    assert skill.human_only_fields == ["IMPLICATION FOR PORTFOLIO"]
    for kind, text in artefacts.items():
        # Field present, instruction present, nothing populated:
        assert check_human_only_fields(text, skill.human_only_fields) == [], (
            f"{kind} artefact violates the human-only field rule"
        )
        # Belt and braces: no line may put content after the field other
        # than the owner-completes instruction.
        for line in text.splitlines():
            m = re.search(r"IMPLICATION FOR PORTFOLIO\W*(.*)", line, re.IGNORECASE)
            if m:
                rest = m.group(1).strip().strip("*_: ")
                assert rest in ("", HUMAN_ONLY_INSTRUCTION), (
                    f"{kind} artefact populated the field: {line!r}"
                )


def test_operator_decision_field_also_enforced(tmp_path):
    d = tmp_path / "opportunity-prioritizer"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\n"
        "name: opportunity-prioritizer\n"
        "description: Score opportunities on a weighted rubric.\n"
        "---\n\n"
        "# Opportunity Prioritizer\n\n"
        "## Method\n"
        "1. Score market size 1-5.\n"
        "2. Score founder fit 1-5.\n"
        "3. Compute the weighted total.\n\n"
        "## Output format\n"
        "- Total score\n"
        "- Operator Decision: (owner fills this in)\n"
    )
    skill = parse_skill_folder(d)
    assert skill.human_only_fields == ["Operator Decision"]
    cls = classify_by_rules(skill)
    core = extract_method_core(skill, cls)
    for kind in KINDS:
        text, _ = generate_artefact(kind, core, portability=cls.verdict)
        assert check_human_only_fields(text, ["Operator Decision"]) == [], (
            f"{kind} artefact violates the Operator Decision rule"
        )


def test_checker_catches_populated_field():
    bad = "IMPLICATION FOR PORTFOLIO: buy more of this stock"
    problems = check_human_only_fields(bad, ["IMPLICATION FOR PORTFOLIO"])
    assert any("filled in" in p for p in problems)


def test_checker_catches_missing_field():
    problems = check_human_only_fields("no field here", ["IMPLICATION FOR PORTFOLIO"])
    assert any("missing" in p for p in problems)


def test_checker_accepts_blank_with_instruction():
    good = f"**IMPLICATION FOR PORTFOLIO:** {HUMAN_ONLY_INSTRUCTION}"
    assert check_human_only_fields(good, ["IMPLICATION FOR PORTFOLIO"]) == []
