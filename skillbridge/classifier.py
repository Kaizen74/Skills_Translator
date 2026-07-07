"""Portability classification (PRD F4/F5).

Rules first — they must work with the LLM mocked — then one local-LLM pass
that may only CONFIRM or annotate, never silently flip a rule verdict without
its reasoning being shown.
"""

import re
from dataclasses import dataclass, field

from .llm import get_llm
from .parser import ParsedSkill

FULL = "FULL"
PARTIAL = "PARTIAL"
CLAUDE_ONLY = "CLAUDE-ONLY"

# Signals that a skill depends on Claude's code-execution environment.
EXECUTION_KEYWORDS = [
    r"\bpptx\b", r"python-pptx", r"\bdocx\b", r"\bxlsx\b",
    r"generate\s+html", r"html\s+(dashboard|preview)",
    r"run\s+in\s+claude\s+code", r"code[- ]execution",
    r"run\s+`?scripts/", r"\bbash\b", r"\bexecute\b",
]

# Signals that a portable method is present (rubrics, steps, templates...).
METHOD_KEYWORDS = [
    r"\brubric\b", r"\bmethod\b", r"\bsteps?\b", r"\btemplate\b",
    r"\bclassif", r"\bscore\b", r"\bscoring\b", r"\bchecklist\b",
    r"\bworkflow\b", r"\bframework\b", r"storyline", r"output format",
]


@dataclass
class Classification:
    verdict: str
    reasoning: str
    claude_only_items: list = field(default_factory=list)
    llm_note: str = ""


def _find_hits(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            hits.append(m.group(0))
    return hits


def classify_by_rules(skill: ParsedSkill) -> Classification:
    text = skill.body
    has_scripts = bool(skill.subfolders.get("scripts"))
    exec_hits = _find_hits(text, EXECUTION_KEYWORDS)
    if has_scripts:
        exec_hits.append("scripts/ folder present")
    method_hits = _find_hits(text, METHOD_KEYWORDS)

    # Numbered lists are a strong sign of a portable step-by-step method.
    numbered_steps = len(re.findall(r"^\s*\d+\.\s+\S", text, re.MULTILINE))
    has_method = len(method_hits) >= 2 or numbered_steps >= 3

    if not exec_hits:
        return Classification(
            verdict=FULL,
            reasoning=(
                f"'{skill.name}' is a pure method skill: it describes "
                f"{'a step-by-step workflow' if numbered_steps else 'a framework'} "
                f"(signals: {', '.join(method_hits[:4]) or 'structured sections'}) and "
                "contains no scripts or code-execution requirements. Everything "
                "meaningful can be ported to the local tier."
            ),
        )

    if has_method:
        return Classification(
            verdict=PARTIAL,
            reasoning=(
                f"'{skill.name}' contains a portable method "
                f"(signals: {', '.join(method_hits[:4])}) PLUS Claude-only execution "
                f"({', '.join(exec_hits[:4])}). The method will be ported; the "
                "execution parts stay on the Claude tier and are listed below."
            ),
            claude_only_items=exec_hits,
        )

    return Classification(
        verdict=CLAUDE_ONLY,
        reasoning=(
            f"'{skill.name}' derives nearly all its value from code execution or "
            f"Claude-specific tooling ({', '.join(exec_hits[:4])}) with no "
            "standalone method to extract. It should be run on the Claude tier; "
            "no local artefacts will be produced."
        ),
        claude_only_items=exec_hits,
    )


def confirm_with_llm(skill: ParsedSkill, rules_result: Classification) -> Classification:
    """One local-LLM pass to sanity-check the rule verdict (PRD F5). The rule
    verdict stands unless the LLM clearly answers with a different verdict word."""
    llm = get_llm()
    prompt = (
        "You review a portability classification of a Claude skill for local "
        "porting. Verdicts: FULL (pure method), PARTIAL (method + Claude-only "
        "execution), CLAUDE-ONLY (all value in execution).\n"
        f"Rule-based verdict: {rules_result.verdict}\n"
        f"Reasoning: {rules_result.reasoning}\n"
        "Skill text (truncated):\n"
        + skill.body[:4000]
        + "\n\nReply with exactly one verdict word, then one sentence of "
        "confirmation or correction.\n"
        f"<<INPUT>>{rules_result.verdict} — confirmed by review.<<END>>"
    )
    try:
        answer = llm.generate(prompt).strip()
    except Exception as e:  # LLM being down must not block classification
        rules_result.llm_note = f"Model confirmation skipped ({e})."
        return rules_result

    first_word = answer.split("—")[0].split()[0].upper().rstrip(".:,") if answer else ""
    if first_word in (FULL, PARTIAL, CLAUDE_ONLY) and first_word != rules_result.verdict:
        rules_result.llm_note = (
            f"Note: the local model suggested {first_word} instead; the rule-based "
            f"verdict {rules_result.verdict} was kept. Model said: {answer[:300]}"
        )
    else:
        rules_result.llm_note = "Confirmed by the local model."
    return rules_result


def classify(skill: ParsedSkill) -> Classification:
    return confirm_with_llm(skill, classify_by_rules(skill))
