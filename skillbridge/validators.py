"""Deterministic validation of generated artefacts (PRD F6-F8, principle 5).

Every artefact passes through here before it is shown to the owner. The
human-only-field check is the hard guarantee behind PRD principle 5: fields
like 'IMPLICATION FOR PORTFOLIO' must exist, must carry the owner-completes
instruction, and must not be populated by the model.
"""

import re

from .parser import HUMAN_ONLY_INSTRUCTION

HERMES_MAX_CHARS = 900
# Qwen system prompt target <= 1,500 tokens; ~4 chars/token heuristic.
PROMPTPACK_SYSTEM_MAX_CHARS = 6000


class ValidationError(Exception):
    pass


def check_human_only_fields(text: str, fields: list[str]) -> list[str]:
    """Return a list of plain-language problems (empty = OK)."""
    problems = []
    for fld in fields:
        pattern = re.compile(re.escape(fld) + r"\s*:?\s*(.*)", re.IGNORECASE)
        matches = pattern.findall(text)
        if not matches:
            problems.append(f"The human-only field '{fld}' is missing from the artefact.")
            continue
        for rest in matches:
            content = rest.strip().strip("*_")
            # The only text allowed after the field name is the instruction
            # (or nothing / a blank marker).
            if content and HUMAN_ONLY_INSTRUCTION.lower() not in content.lower() \
                    and content not in ("(", ")", "-", "—", ":"):
                problems.append(
                    f"The human-only field '{fld}' has been filled in by the model "
                    f"('{content[:60]}...') — it must stay blank for the owner."
                )
        if not any(HUMAN_ONLY_INSTRUCTION.lower() in m.lower() for m in matches):
            problems.append(
                f"The human-only field '{fld}' is missing the instruction "
                f"'{HUMAN_ONLY_INSTRUCTION}'"
            )
    return problems


def validate_hermes(text: str, core: dict) -> list[str]:
    problems = []
    if len(text) > HERMES_MAX_CHARS:
        problems.append(
            f"The standing rule is {len(text)} characters; Hermes rules must be "
            f"{HERMES_MAX_CHARS} or fewer."
        )
    if not text.lower().startswith("standing rule"):
        problems.append("The message must start with 'Standing rule'.")
    if core.get("trigger") and core["trigger"].lower() not in text.lower():
        problems.append(f"The trigger phrase '{core['trigger']}' is missing.")
    problems += check_human_only_fields(text, core.get("human_only_fields", []))
    return problems


def validate_obsidian(text: str, core: dict) -> list[str]:
    problems = []
    if not re.match(r"^---\s*\n.*?\n---", text, re.DOTALL):
        problems.append("The template is missing its YAML frontmatter block.")
    for key in ("skill_source", "skill_version", "ported_date", "portability"):
        if key + ":" not in text:
            problems.append(f"Frontmatter is missing the '{key}' field.")
    problems += check_human_only_fields(text, core.get("human_only_fields", []))
    return problems


def validate_promptpack(text: str, core: dict) -> list[str]:
    problems = []
    for section in ("## System prompt", "## User prompt scaffold", "## When to escalate to Claude"):
        if section.lower() not in text.lower():
            problems.append(f"The prompt pack is missing the '{section}' section.")
    m = re.search(r"## System prompt\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
    if m and len(m.group(1)) > PROMPTPACK_SYSTEM_MAX_CHARS:
        problems.append(
            "The system prompt block is too long for Qwen "
            f"(~{len(m.group(1)) // 4} tokens; target is 1,500)."
        )
    problems += check_human_only_fields(text, core.get("human_only_fields", []))
    return problems


VALIDATORS = {
    "hermes": validate_hermes,
    "obsidian": validate_obsidian,
    "promptpack": validate_promptpack,
}


def validate(kind: str, text: str, core: dict) -> list[str]:
    return VALIDATORS[kind](text, core)
