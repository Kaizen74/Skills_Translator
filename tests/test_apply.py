from pathlib import Path

from skillbridge import config
from skillbridge.apply import (
    apply_obsidian,
    apply_promptpack,
    atomic_write,
    registry_append,
    registry_read,
    registry_update_status,
    versioned_path,
)
from skillbridge.diffing import diff_method_cores


def test_template_written_into_vault(isolated_env):
    path, msg = apply_obsidian("pkm-processor", "---\ncontent\n---\nbody")
    assert path == isolated_env["vault"] / "_TEMPLATE_pkm-processor.md"
    assert path.read_text() == "---\ncontent\n---\nbody"
    assert "saved into your vault" in msg


def test_never_overwrites_existing_template(isolated_env):
    p1, _ = apply_obsidian("pkm-processor", "first version")
    p2, msg = apply_obsidian("pkm-processor", "second version")
    assert p1.read_text() == "first version"  # untouched
    assert p2.name == "_TEMPLATE_pkm-processor_v2.md"
    assert "nothing was overwritten" in msg
    p3, _ = apply_obsidian("pkm-processor", "third")
    assert p3.name == "_TEMPLATE_pkm-processor_v3.md"


def test_promptpack_saved_to_library(isolated_env):
    path, msg = apply_promptpack("pkm-processor", "pack content")
    assert path.parent == config.library_dir()
    assert path.read_text() == "pack content"


def test_atomic_write_leaves_no_temp_files(tmp_path):
    target = tmp_path / "sub" / "file.md"
    atomic_write(target, "hello")
    assert target.read_text() == "hello"
    leftovers = [p for p in target.parent.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_versioned_path_strips_old_suffix(tmp_path):
    (tmp_path / "note.md").touch()
    (tmp_path / "note_v2.md").touch()
    p, renamed = versioned_path(tmp_path / "note.md")
    assert p.name == "note_v3.md" and renamed


def test_registry_append_and_read(isolated_env):
    registry_append("pkm-processor", 1, "FULL", ["template", "prompt pack", "standing rule"])
    text = registry_read()
    assert "# Skill Porting Registry" in text
    assert "| pkm-processor | v1 |" in text
    assert "FULL" in text and "Drafted" in text
    registry_append("deck-studio", 1, "PARTIAL", ["template"])
    text = registry_read()
    assert text.count("| pkm-processor") == 1 and "| deck-studio" in text
    # Registry lives in the vault's Synthesis folder (PRD F12)
    assert (isolated_env["vault"] / "Synthesis" / "Skill-Porting-Registry.md").exists()


def test_registry_status_update(isolated_env):
    registry_append("pkm-processor", 1, "FULL", ["template"])
    assert registry_update_status("pkm-processor", 1, "Rule sent")
    assert "Rule sent" in registry_read()
    assert not registry_update_status("nonexistent", 9, "x")


def test_diff_method_cores():
    old = {"purpose": "a", "steps": ["one", "two"], "trigger": "go",
           "output_format": "x", "rubric": [], "human_only_fields": []}
    new = dict(old, steps=["one", "three"], trigger="run")
    summary = diff_method_cores(old, new)
    assert "New step: three" in summary
    assert "Removed step: two" in summary
    assert "'go' to 'run'" in summary
    assert diff_method_cores(old, dict(old)) == "No meaningful changes to the method were detected."
    assert diff_method_cores({}, new) == ""
