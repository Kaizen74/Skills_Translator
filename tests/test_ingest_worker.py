import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from skillbridge import config, db
from skillbridge.ingest import (
    IngestError,
    InboxWatcher,
    ingest_md_bytes,
    ingest_upload,
    ingest_zip_bytes,
    extract_zip,
)
from skillbridge.worker import drain_queue


def zip_of(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in folder.rglob("*"):
            if p.is_file():
                zf.write(p, f"{folder.name}/{p.relative_to(folder)}")
    return buf.getvalue()


def test_zip_ingest_and_full_port(fixture_skill):
    skill_id = ingest_zip_bytes(zip_of(fixture_skill("pkm-processor")), "pkm-processor.zip")
    drain_queue()
    row = db.get_skill(skill_id)
    assert row["status"] == "ready"
    assert row["verdict"] == "FULL"
    arts = {a["kind"]: a for a in db.get_artefacts(skill_id)}
    assert set(arts) == {"hermes", "obsidian", "promptpack"}
    # Intermediate method-core JSON saved for auditability (PRD F9)
    core_files = list(config.work_dir().glob("method-core-pkm-processor-v1.json"))
    assert len(core_files) == 1
    core = json.loads(core_files[0].read_text())
    assert core["human_only_fields"] == ["IMPLICATION FOR PORTFOLIO"]


def test_single_md_file_upload_ports_fully(fixture_skill):
    md = (fixture_skill("pkm-processor") / "SKILL.md").read_bytes()
    skill_id = ingest_md_bytes(md, "pkm-processor.md")
    drain_queue()
    row = db.get_skill(skill_id)
    assert row["status"] == "ready"
    assert row["verdict"] == "FULL"
    arts = {a["kind"]: a for a in db.get_artefacts(skill_id)}
    assert set(arts) == {"hermes", "obsidian", "promptpack"}


def test_ingest_upload_routes_by_extension(fixture_skill):
    src = fixture_skill("pkm-processor")
    md = (src / "SKILL.md").read_bytes()
    # .md route
    md_id = ingest_upload(md, "whatever-name.md")
    assert db.get_skill(md_id)["name"] == "pkm-processor"
    # .zip route
    zip_id = ingest_upload(zip_of(fixture_skill("deck-studio")), "deck-studio.zip")
    assert db.get_skill(zip_id)["name"] == "deck-studio"


def test_ingest_upload_rejects_other_file_types(fixture_skill):
    with pytest.raises(IngestError, match=r"\.zip.*\.md|ZIP.*single skill file"):
        ingest_upload(b"some text", "notes.txt")


def test_md_without_frontmatter_rejected_plainly():
    with pytest.raises(IngestError, match="header block"):
        ingest_md_bytes(b"# Just a heading, no frontmatter\n", "loose.md")


def test_inbox_watcher_picks_up_dropped_md_file(fixture_skill):
    md = (fixture_skill("pkm-processor") / "SKILL.md").read_bytes()
    dropped = config.inbox_dir() / "pkm-processor.md"
    dropped.write_bytes(md)
    watcher = InboxWatcher()
    ids = watcher.scan_once()
    if not ids:  # file may look "still being copied" for a moment
        import time
        time.sleep(2.1)
        ids = watcher.scan_once()
    assert len(ids) == 1
    assert not dropped.exists()  # consumed from the inbox
    drain_queue()
    assert db.get_skill(ids[0])["status"] == "ready"


def test_claude_only_skill_gets_registry_line_and_no_artefacts(fixture_skill):
    skill_id = ingest_zip_bytes(zip_of(fixture_skill("pptx-toolkit")), "pptx-toolkit.zip")
    drain_queue()
    row = db.get_skill(skill_id)
    assert row["status"] == "claude-only"
    assert db.get_artefacts(skill_id) == []
    from skillbridge.apply import registry_read
    assert "Run on Claude tier" in registry_read()


def test_bad_zip_rejected_with_plain_language():
    with pytest.raises(IngestError, match="valid ZIP"):
        ingest_zip_bytes(b"not a zip at all", "junk.zip")


def test_zip_with_traversal_rejected(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", "bad")
    with pytest.raises(IngestError, match="unsafe"):
        extract_zip(buf.getvalue(), "evil.zip")


def test_zip_without_skill_md_rejected(tmp_path):
    d = tmp_path / "noskill"
    d.mkdir()
    (d / "readme.txt").write_text("hello")
    with pytest.raises(IngestError, match="No SKILL.md"):
        ingest_zip_bytes(zip_of(d), "noskill.zip")


def test_inbox_watcher_picks_up_dropped_folder(fixture_skill):
    src = fixture_skill("pkm-processor")
    dest = config.inbox_dir() / "pkm-processor"
    shutil.copytree(src, dest)
    watcher = InboxWatcher()
    ids = watcher.scan_once()
    if not ids:  # folder may look "still being copied" for a moment
        import time
        time.sleep(2.1)
        ids = watcher.scan_once()
    assert len(ids) == 1
    assert not dest.exists()  # moved out of the inbox
    drain_queue()
    assert db.get_skill(ids[0])["status"] == "ready"


def test_reboot_resumability(fixture_skill):
    # A job left 'running' by a crash must be re-queued at startup (PRD N4).
    skill_id = ingest_zip_bytes(zip_of(fixture_skill("pkm-processor")), "pkm.zip")
    job = db.next_queued_job()
    db.update_job(job["id"], status="running")
    assert db.next_queued_job() is None  # simulated crash mid-job
    assert db.requeue_interrupted_jobs() == 1
    drain_queue()
    assert db.get_skill(skill_id)["status"] == "ready"


def test_reingest_produces_v2_with_diff(fixture_skill, tmp_path):
    src = fixture_skill("pkm-processor")
    skill_id_1 = ingest_zip_bytes(zip_of(src), "pkm.zip")
    drain_queue()
    # The owner edits the skill and drops it in again (PRD F13)
    text = (src / "SKILL.md").read_text().replace(
        "5. Draft the filed note using the output format below.",
        "5. Draft the filed note using the output format below.\n"
        "6. Flag any claim that contradicts an existing note.",
    )
    (src / "SKILL.md").write_text(text)
    skill_id_2 = ingest_zip_bytes(zip_of(src), "pkm.zip")
    drain_queue()
    row = db.get_skill(skill_id_2)
    assert row["version"] == 2
    assert "New step" in row["diff_summary"]
    # v1 artefacts are untouched (never deleted)
    assert db.get_artefacts(skill_id_1)


def test_confidential_keyword_halts_skill(fixture_skill):
    cfg = config.load_config()
    cfg["confidential_keywords"] = ["Project Nightjar"]
    config.save_config(cfg)
    src = fixture_skill("pkm-processor")
    text = (src / "SKILL.md").read_text() + "\nRelates to Project Nightjar.\n"
    (src / "SKILL.md").write_text(text)
    skill_id = ingest_zip_bytes(zip_of(src), "pkm.zip")
    drain_queue()
    row = db.get_skill(skill_id)
    assert row["status"] == "halted"
    assert "Project Nightjar" in row["error"]
    assert db.get_artefacts(skill_id) == []
