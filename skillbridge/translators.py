"""The three translators (PRD F6/F7/F8).

All three render from the same method core (PRD F9). Each has a deterministic
renderer that always produces a VALID artefact; a local-LLM polish pass (with
optional owner steering) may improve the wording, but its output is accepted
only if it passes the validators — otherwise the deterministic draft stands.
This guarantees the owner always gets a reviewable, rule-compliant draft even
if the model misbehaves or is unavailable.
"""

import re
from datetime import date

from .llm import get_llm
from .parser import HUMAN_ONLY_INSTRUCTION
from .validators import HERMES_MAX_CHARS, validate

KINDS = ("hermes", "obsidian", "promptpack")


def blank_human_only_lines(text: str, fields: list[str]) -> str:
    """Rewrite any line mentioning a human-only field to the canonical blank
    form, so source snippets can never smuggle in filled content."""
    if not fields:
        return text
    lines = []
    for line in text.splitlines():
        replaced = False
        for fld in fields:
            if re.search(re.escape(fld), line, re.IGNORECASE):
                lines.append(f"{fld}: {HUMAN_ONLY_INSTRUCTION}")
                replaced = True
                break
        if not replaced:
            lines.append(line)
    return "\n".join(lines)


def _human_only_clause(fields: list[str]) -> str:
    return " ".join(f"{fld}: {HUMAN_ONLY_INSTRUCTION}" for fld in fields)


# --- Hermes standing rule (F6) ---------------------------------------------

def render_hermes(core: dict) -> str:
    trigger = core["trigger"]
    fields = core.get("human_only_fields", [])
    steps = core.get("steps") or [core["purpose"]]
    condensed = "; ".join(s.rstrip(".") for s in steps[:6])
    # Human-only field lines are removed from the reply-format summary here;
    # the rule carries them once, as the explicit blank-field clause (tail).
    fmt_lines = [
        ln for ln in core.get("output_format", "").splitlines()
        if not any(re.search(re.escape(f), ln, re.IGNORECASE) for f in fields)
    ]
    reply = " ".join("\n".join(fmt_lines).split())
    reply = re.sub(r"[#*`]", "", reply)[:220] or "a short structured summary"
    tail = ""
    if core.get("human_only_fields"):
        tail = " " + _human_only_clause(core["human_only_fields"])

    def build(condensed_steps: str) -> str:
        return (
            f"Standing rule — '{trigger}': when I send content starting "
            f"'{trigger}:', {condensed_steps}, and reply with: {reply}.{tail}"
        )

    text = build(condensed)
    while len(text) > HERMES_MAX_CHARS and len(steps) > 1:
        steps = steps[:-1]
        condensed = "; ".join(s.rstrip(".") for s in steps)
        text = build(condensed)
    if len(text) > HERMES_MAX_CHARS:
        overshoot = len(text) - HERMES_MAX_CHARS + 3
        text = build(condensed[: max(20, len(condensed) - overshoot)] + "…")
    return text


# --- Obsidian template (F7) -------------------------------------------------

def render_obsidian(core: dict, version: int = 1, portability: str = "FULL") -> str:
    steps = "\n".join(f"- [ ] {s}" for s in core.get("steps", [])) or "- [ ] Apply the method."
    out_fmt = blank_human_only_lines(
        core.get("output_format", ""), core.get("human_only_fields", [])
    )
    human_only = "\n".join(
        f"**{fld}:** {HUMAN_ONLY_INSTRUCTION}\n" for fld in core.get("human_only_fields", [])
    )
    parts = [
        "---",
        f"skill_source: {core['name']}",
        f"skill_version: {version}",
        f"ported_date: {date.today().isoformat()}",
        f"portability: {portability}",
        "---",
        "",
        f"# {core['name'].replace('-', ' ').title()}",
        "",
        f"> {core['purpose']}",
        "",
        "## Method",
        steps,
        "",
        "## Work area",
        "_Fill in below while applying the method._",
        "",
    ]
    if out_fmt:
        parts += ["## Output", out_fmt, ""]
    parts += ["## Links", "- Related: [[ ]]", ""]
    if human_only:
        parts += [human_only]
    if core.get("escalation"):
        parts += [f"_Escalation: {core['escalation']}_", ""]
    return "\n".join(parts)


# --- Qwen prompt pack (F8) ---------------------------------------------------

def render_promptpack(core: dict, portability: str = "FULL") -> str:
    fields = core.get("human_only_fields", [])
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(core.get("steps", []), 1))
    system_lines = [
        f"You apply the '{core['name']}' method.",
        f"Purpose: {core['purpose']}",
    ]
    if steps:
        system_lines += ["Follow these steps exactly:", steps]
    if core.get("rubric"):
        system_lines.append(
            "Rubric dimensions and weights: "
            + "; ".join(f"{d['dimension']} ({d['weight']}%)" for d in core["rubric"])
        )
    if core.get("output_format"):
        system_lines += [
            "Reply in this format:",
            blank_human_only_lines(core["output_format"], fields),
        ]
    if fields:
        system_lines.append(
            "Some fields are for the human owner only and you must never fill them. "
            + _human_only_clause(fields)
        )
    system_lines.append("Never invent facts, sources, or examples.")
    system = "\n".join(system_lines)

    parts = [
        f"# Prompt pack — {core['name']}",
        f"_Ported {date.today().isoformat()} · portability: {portability} · "
        "for the local Qwen model via Ollama_",
        "",
        "## System prompt",
        "```",
        system[:5800],
        "```",
        "",
        "## User prompt scaffold",
        "```",
        f"{core.get('trigger', core['name'])}: <paste your content here>",
        "```",
        "",
    ]
    examples = core.get("examples", [])
    if examples:
        parts += ["## Few-shot examples", "_Taken from the source skill — not invented._", ""]
        for ex in examples[:2]:
            parts += ["```", blank_human_only_lines(ex.strip(), fields), "```", ""]
    parts += [
        "## When to escalate to Claude",
        core.get("escalation")
        or "Escalate when the task needs deep multi-document synthesis.",
        "",
    ]
    return "\n".join(parts)


# --- Common entry point -------------------------------------------------------

def render(kind: str, core: dict, version: int = 1, portability: str = "FULL") -> str:
    if kind == "hermes":
        return render_hermes(core)
    if kind == "obsidian":
        return render_obsidian(core, version=version, portability=portability)
    if kind == "promptpack":
        return render_promptpack(core, portability=portability)
    raise ValueError(f"Unknown artefact kind: {kind}")


def generate_artefact(
    kind: str,
    core: dict,
    version: int = 1,
    portability: str = "FULL",
    steering: str = "",
) -> tuple[str, str]:
    """Return (artefact_text, note). The note explains, in plain language,
    whether the model's polish was used or the deterministic draft kept."""
    draft = render(kind, core, version=version, portability=portability)
    llm = get_llm()
    steer_line = f"\nOwner's steering note (must be honoured): {steering}\n" if steering else ""
    prompt = (
        f"Polish this generated artefact of kind '{kind}'. Keep the exact same "
        "structure, sections and any YAML frontmatter. Improve clarity only. "
        "Human-only fields must stay blank with their instruction line. "
        f"Hermes rules must stay under {HERMES_MAX_CHARS} characters."
        + steer_line
        + f"\n<<INPUT>>{draft}<<END>>"
    )
    try:
        polished = llm.generate(prompt).strip()
    except Exception as e:
        return draft, f"Draft generated locally without model polish ({e})."

    if polished and not validate(kind, polished, core):
        return polished, "Draft polished by the local model and validated."
    return draft, (
        "The model's version failed validation, so the safe deterministic "
        "draft is shown instead."
    )
