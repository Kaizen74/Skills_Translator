"""Re-port diffing (PRD F13): when a skill is ingested again, show the owner
what changed in the method core, in plain language."""


def diff_method_cores(old: dict, new: dict) -> str:
    if not old:
        return ""
    lines = []
    if old.get("purpose") != new.get("purpose"):
        lines.append("The purpose wording changed.")
    old_steps, new_steps = old.get("steps", []), new.get("steps", [])
    added = [s for s in new_steps if s not in old_steps]
    removed = [s for s in old_steps if s not in new_steps]
    for s in added:
        lines.append(f"New step: {s}")
    for s in removed:
        lines.append(f"Removed step: {s}")
    if old.get("output_format") != new.get("output_format"):
        lines.append("The output format changed.")
    if old.get("rubric") != new.get("rubric"):
        lines.append("The rubric dimensions or weights changed.")
    if old.get("trigger") != new.get("trigger"):
        lines.append(
            f"The trigger phrase changed from '{old.get('trigger')}' to '{new.get('trigger')}'."
        )
    if set(old.get("human_only_fields", [])) != set(new.get("human_only_fields", [])):
        lines.append("The human-only fields changed.")
    if not lines:
        return "No meaningful changes to the method were detected."
    return "\n".join(f"- {l}" for l in lines)
