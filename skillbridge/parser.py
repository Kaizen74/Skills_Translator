"""Parse a Claude skill folder: SKILL.md frontmatter + body, subfolder inventory.

Nothing here executes skill content — scripts and assets are only listed
(PRD F2). Errors are raised as SkillParseError with a plain-language message
that the UI shows verbatim (PRD F3).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Fields that only the owner may fill in. Detected deterministically from the
# SOURCE skill text; generated artefacts must render them blank (PRD principle 5).
HUMAN_ONLY_FIELDS = ["IMPLICATION FOR PORTFOLIO", "Operator Decision"]

HUMAN_ONLY_INSTRUCTION = "Leave blank — owner completes."


class SkillParseError(Exception):
    """Plain-language parse failure, safe to show to the owner."""


@dataclass
class ParsedSkill:
    name: str
    description: str
    body: str
    source_dir: str
    subfolders: dict = field(default_factory=dict)  # {"scripts": ["run.py"], ...}
    human_only_fields: list = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return self.body


def find_skill_md(folder: Path) -> Path | None:
    """SKILL.md may be at the top level or one directory down (zip-of-a-folder)."""
    direct = folder / "SKILL.md"
    if direct.exists():
        return direct
    candidates = sorted(folder.glob("*/SKILL.md"))
    if candidates:
        return candidates[0]
    return None


def detect_human_only_fields(text: str) -> list[str]:
    found = []
    for fld in HUMAN_ONLY_FIELDS:
        if re.search(re.escape(fld), text, re.IGNORECASE):
            found.append(fld)
    return found


def parse_skill_folder(folder: str | Path) -> ParsedSkill:
    folder = Path(folder)
    skill_md = find_skill_md(folder)
    if skill_md is None:
        raise SkillParseError(
            "No SKILL.md file was found in this folder. A Claude skill always "
            "contains a file named SKILL.md — please check the folder and try again."
        )

    raw = skill_md.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not match:
        raise SkillParseError(
            "The SKILL.md file is missing its header block (the section between "
            "'---' lines at the top that names the skill). The skill can't be "
            "read without it."
        )

    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        raise SkillParseError(
            "The header block at the top of SKILL.md is malformed and could not "
            "be read. Please re-download or fix the skill file."
        )

    if not isinstance(meta, dict) or not meta.get("name"):
        raise SkillParseError(
            "The SKILL.md header block does not contain a 'name' field, so the "
            "skill can't be identified."
        )

    body = match.group(2)
    base = skill_md.parent
    subfolders = {}
    for sub in ("references", "scripts", "assets"):
        d = base / sub
        if d.is_dir():
            subfolders[sub] = sorted(
                str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()
            )

    # Include reference text in the human-only-field scan: the field may live
    # in a template under references/ rather than in the SKILL.md body.
    scan_text = body
    for ref in subfolders.get("references", []):
        try:
            scan_text += "\n" + (base / "references" / ref).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            pass

    return ParsedSkill(
        name=str(meta.get("name")),
        description=str(meta.get("description") or ""),
        body=body,
        source_dir=str(base),
        subfolders=subfolders,
        human_only_fields=detect_human_only_fields(scan_text),
    )
