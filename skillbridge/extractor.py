"""Method-core extraction (PRD F9).

The method core is the single intermediate JSON that all three translators
render from: purpose, trigger, steps, rubric, output format, human-only
fields, escalation line, examples.

Extraction is a deterministic structural draft (headings, numbered lists,
bullets) refined by one local-LLM pass. Human-only fields and examples are
ALWAYS taken deterministically from the source — the LLM may not add or
remove them (PRD principle 5; F8 'never invent examples').
"""

import json
import re

from .classifier import Classification
from .llm import get_llm
from .parser import ParsedSkill


def _section(body: str, *names: str) -> str:
    """Return the text under the first markdown heading matching any name."""
    for name in names:
        m = re.search(
            rf"^#{{1,4}}\s*{name}[^\n]*\n(.*?)(?=^#{{1,4}}\s|\Z)",
            body, re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        if m:
            return m.group(1).strip()
    return ""


def _numbered_steps(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^\s*\d+\.\s+(.+)$", text, re.MULTILINE)]


def _rubric_dimensions(body: str) -> list[dict]:
    """Detect 'Dimension (weight N%)' or 'Dimension — weight N' style rubric lines."""
    dims = []
    for m in re.finditer(
        r"^[-*]\s*\*{0,2}([^:*\n]+?)\*{0,2}\s*[—:-]?\s*\(?weight[:\s]*(\d+)\s*%?\)?",
        body, re.IGNORECASE | re.MULTILINE,
    ):
        dims.append({"dimension": m.group(1).strip(), "weight": int(m.group(2))})
    return dims


def _examples(body: str) -> list[str]:
    """Only real examples from the skill itself — never invented (PRD F8)."""
    ex = _section(body, "Examples?", "Few-shot", "Sample")
    if not ex:
        return []
    return [ex[:2000]]


def draft_method_core(skill: ParsedSkill, classification: Classification) -> dict:
    body = skill.body
    steps = (
        _numbered_steps(_section(body, "Method", "Steps", "Workflow", "Process", "Storyline method"))
        or _numbered_steps(body)
    )
    purpose = _section(body, "Purpose", "Overview") or skill.description
    trigger_text = _section(body, "When to use", "Trigger", "Usage")
    m = re.search(r'["“]([^"”]{2,40})[:”"]', trigger_text)
    trigger = m.group(1).strip().rstrip(":") if m else skill.name.replace("-", " ")
    escalation = _section(body, "Escalation", "When to escalate")

    return {
        "name": skill.name,
        "purpose": " ".join(purpose.split())[:500],
        "trigger": trigger,
        "steps": steps[:12],
        "rubric": _rubric_dimensions(body),
        "output_format": _section(body, "Output format", "Output", "Reply format")[:1500],
        "human_only_fields": list(skill.human_only_fields),
        "escalation": " ".join(escalation.split())[:400]
        or (
            "Escalate to the Claude tier for: "
            + "; ".join(classification.claude_only_items[:5])
            if classification.claude_only_items
            else "Escalate to the Claude tier when the task needs deep multi-document synthesis."
        ),
        "examples": _examples(body),
        "claude_only_items": list(classification.claude_only_items),
    }


def refine_with_llm(skill: ParsedSkill, draft: dict) -> dict:
    """One local-LLM pass to improve wording of purpose/steps. Structure and
    the protected fields are re-imposed deterministically afterwards."""
    llm = get_llm()
    draft_json = json.dumps(draft, indent=1)
    prompt = (
        "Refine this extracted 'method core' of a Claude skill. Keep the exact "
        "same JSON keys. Improve wording of purpose and steps so they stand "
        "alone without the original document. Do not add examples. Do not fill "
        "human-only fields. Return JSON only.\n"
        "Skill text:\n" + skill.body[:6000] + "\n\n"
        f"<<INPUT>>{draft_json}<<END>>"
    )
    try:
        raw = llm.generate(prompt, as_json=True)
        refined = json.loads(raw)
        if not isinstance(refined, dict):
            raise ValueError("not a dict")
    except Exception:
        # A bad model response never blocks the pipeline; the deterministic
        # draft is already a valid method core.
        return draft

    core = dict(draft)
    for key in ("purpose", "steps", "output_format", "trigger", "escalation"):
        if key in refined and type(refined[key]) is type(draft[key]) and refined[key]:
            core[key] = refined[key]
    # Protected fields always come from the deterministic pass:
    core["name"] = draft["name"]
    core["human_only_fields"] = draft["human_only_fields"]
    core["examples"] = draft["examples"]
    core["claude_only_items"] = draft["claude_only_items"]
    core["steps"] = [str(s) for s in core["steps"]][:12]
    return core


def extract_method_core(skill: ParsedSkill, classification: Classification) -> dict:
    return refine_with_llm(skill, draft_method_core(skill, classification))
