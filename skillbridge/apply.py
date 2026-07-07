"""Applying approved artefacts (PRD F11) and the porting registry (F12).

Rules enforced here:
- Atomic writes: temp file in the same directory, then os.replace (PRD N4).
- Never overwrite: existing filenames get a _v2 / _v3 ... suffix, and the
  caller is told so in plain language.
"""

import os
import re
import tempfile
from pathlib import Path

from . import config, db


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def versioned_path(path: Path) -> tuple[Path, bool]:
    """Return a path that does not exist yet. (path, was_renamed)."""
    if not path.exists():
        return path, False
    stem, suffix = path.stem, path.suffix
    base = re.sub(r"_v\d+$", "", stem)
    n = 2
    while True:
        candidate = path.parent / f"{base}_v{n}{suffix}"
        if not candidate.exists():
            return candidate, True
        n += 1


def apply_obsidian(skill_name: str, content: str, dest_dir: str | Path | None = None) -> tuple[Path, str]:
    """Write the approved template into the vault. Returns (path, plain message)."""
    dest = Path(dest_dir).expanduser() if dest_dir else config.vault_path()
    target = dest / f"_TEMPLATE_{skill_name}.md"
    target, renamed = versioned_path(target)
    atomic_write(target, content)
    if renamed:
        msg = (
            f"A template with that name already existed, so nothing was overwritten — "
            f"the new one was saved as {target.name}."
        )
    else:
        msg = f"Template saved into your vault as {target.name}."
    return target, msg


def apply_promptpack(skill_name: str, content: str) -> tuple[Path, str]:
    config.ensure_dirs()
    target = config.library_dir() / f"{skill_name}.md"
    target, renamed = versioned_path(target)
    atomic_write(target, content)
    msg = f"Prompt pack saved to the library as {target.name}."
    if renamed:
        msg = f"A prompt pack with that name already existed — saved as {target.name} instead."
    return target, msg


# --- Registry (F12) ---------------------------------------------------------

REGISTRY_HEADER = """# Skill Porting Registry

Every Claude skill ported by SkillBridge, one row per version. Edit the
Status column by hand or from the SkillBridge UI.

| Skill | Version | Ported | Portability | Artefacts | Status |
|---|---|---|---|---|---|
"""


def registry_append(skill_name: str, version: int, verdict: str,
                    artefacts: list[str], status: str = "Drafted") -> Path:
    path = config.registry_path()
    existing = path.read_text(encoding="utf-8") if path.exists() else REGISTRY_HEADER
    if not existing.endswith("\n"):
        existing += "\n"
    row = (
        f"| {skill_name} | v{version} | {db.now()[:10]} | {verdict} | "
        f"{', '.join(artefacts) or '—'} | {status} |\n"
    )
    atomic_write(path, existing + row)
    return path


def registry_read() -> str:
    path = config.registry_path()
    return path.read_text(encoding="utf-8") if path.exists() else REGISTRY_HEADER


def registry_update_status(skill_name: str, version: int, new_status: str) -> bool:
    """Update the Status cell of one row. Returns True if a row was changed."""
    path = config.registry_path()
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 7 and cells[1] == skill_name and cells[2] == f"v{version}":
            cells[6] = new_status
            lines[i] = "| " + " | ".join(cells[1:7]) + " |\n"
            changed = True
    if changed:
        atomic_write(path, "".join(lines))
    return changed
