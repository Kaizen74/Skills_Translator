"""End-to-end mock run (PRD N1/N2, acceptance criterion 1): upload a skill ZIP
through the web app, wait for drafts, approve all three artefacts, and verify
the template landed in the vault, the pack in the library, the rule is
copy-ready, and the registry recorded it — all with zero model load.
"""

import io
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from skillbridge import config, db
from skillbridge.app import app

FIXTURES = Path(__file__).parent / "fixtures"


def zip_of(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in folder.rglob("*"):
            if p.is_file():
                zf.write(p, f"{folder.name}/{p.relative_to(folder)}")
    return buf.getvalue()


def wait_ready(client, skill_id, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = client.get(f"/api/skill/{skill_id}/status").json()
        if j["status"] in ("ready", "error", "claude-only", "halted"):
            return j
        time.sleep(0.2)
    raise AssertionError("timed out waiting for the background worker")


def test_full_review_cycle_through_the_browser(isolated_env):
    with TestClient(app) as client:
        # Home screen loads with health line
        home = client.get("/")
        assert home.status_code == 200
        assert "SkillBridge" in home.text and "Health" in home.text

        # Upload the pkm-processor ZIP
        r = client.post("/upload", files={
            "file": ("pkm-processor.zip", zip_of(FIXTURES / "pkm-processor"), "application/zip")
        }, follow_redirects=False)
        assert r.status_code == 303
        skill_id = db.list_skills()[0]["id"]

        status = wait_ready(client, skill_id)
        assert status["status"] == "ready"

        # Review screen shows verdict + three editable drafts
        review = client.get(f"/skill/{skill_id}")
        assert "Portability verdict" in review.text
        assert "FULL" in review.text
        assert "Standing rule" in review.text
        assert "IMPLICATION FOR PORTFOLIO" in review.text

        # Approve the Obsidian template -> filed into the vault
        art = db.get_artefact(skill_id, "obsidian")
        client.post(f"/skill/{skill_id}/approve/obsidian",
                    data={"content": art["content"], "dest_dir": ""})
        vault_file = config.vault_path() / "_TEMPLATE_pkm-processor.md"
        assert vault_file.exists()
        assert "Leave blank — owner completes." in vault_file.read_text()

        # Approve the prompt pack -> saved to the library
        art = db.get_artefact(skill_id, "promptpack")
        client.post(f"/skill/{skill_id}/approve/promptpack", data={"content": art["content"]})
        assert (config.library_dir() / "pkm-processor.md").exists()

        # Approve the standing rule -> becomes copy-ready with instructions
        art = db.get_artefact(skill_id, "hermes")
        client.post(f"/skill/{skill_id}/approve/hermes", data={"content": art["content"]})
        review = client.get(f"/skill/{skill_id}")
        assert "Paste this into your Hermes Telegram chat once" in review.text
        assert "Copy" in review.text

        # All approved -> skill done, registry shows it
        assert db.get_skill(skill_id)["status"] == "done"
        reg = client.get("/registry")
        assert "pkm-processor" in reg.text and "Approved" in reg.text

        # Mark rule as sent from the UI (F12 status edit)
        client.post(f"/skill/{skill_id}/rule-sent")
        assert "Rule sent" in client.get("/registry").text


def test_upload_single_md_file_through_the_browser(isolated_env):
    md_bytes = (FIXTURES / "pkm-processor" / "SKILL.md").read_bytes()
    with TestClient(app) as client:
        r = client.post("/upload", files={
            "file": ("pkm-processor.md", md_bytes, "text/markdown")
        }, follow_redirects=False)
        assert r.status_code == 303
        skill_id = db.list_skills()[0]["id"]
        assert wait_ready(client, skill_id)["status"] == "ready"
        review = client.get(f"/skill/{skill_id}")
        assert "FULL" in review.text
        # Approve the template -> filed into the vault, same as the ZIP path
        art = db.get_artefact(skill_id, "obsidian")
        client.post(f"/skill/{skill_id}/approve/obsidian",
                    data={"content": art["content"], "dest_dir": ""})
        assert (config.vault_path() / "_TEMPLATE_pkm-processor.md").exists()


def test_home_page_offers_md_upload(isolated_env):
    with TestClient(app) as client:
        home = client.get("/")
        assert ".md" in home.text
        assert 'accept=".zip,.md,.markdown"' in home.text


def test_partial_skill_shows_claude_only_list(isolated_env):
    with TestClient(app) as client:
        client.post("/upload", files={
            "file": ("deck-studio.zip", zip_of(FIXTURES / "deck-studio"), "application/zip")
        })
        skill_id = db.list_skills()[0]["id"]
        status = wait_ready(client, skill_id)
        assert status["status"] == "ready"
        review = client.get(f"/skill/{skill_id}")
        assert "PARTIAL" in review.text
        assert "Stays on the Claude tier" in review.text


def test_regenerate_with_steering_through_ui(isolated_env):
    with TestClient(app) as client:
        client.post("/upload", files={
            "file": ("pkm.zip", zip_of(FIXTURES / "pkm-processor"), "application/zip")
        })
        skill_id = db.list_skills()[0]["id"]
        wait_ready(client, skill_id)
        r = client.post(f"/skill/{skill_id}/regenerate/hermes",
                        data={"steering": "shorter"}, follow_redirects=False)
        assert r.status_code == 303
        deadline = time.time() + 10
        while time.time() < deadline:
            job = db.latest_job_for_skill(skill_id)
            if job["action"] == "regenerate" and job["status"] == "done":
                break
            time.sleep(0.2)
        assert db.get_artefact(skill_id, "hermes")["content"].startswith("Standing rule")


def test_bad_upload_shows_plain_error(isolated_env):
    with TestClient(app) as client:
        r = client.post("/upload", files={
            "file": ("junk.zip", b"this is not a zip", "application/zip")
        }, follow_redirects=True)
        assert "valid ZIP" in r.text


def test_settings_and_health(isolated_env):
    with TestClient(app) as client:
        s = client.get("/settings")
        assert "Obsidian vault folder" in s.text
        h = client.get("/api/health").json()
        assert h["ollama_ok"] is True  # mock mode
        assert h["vault_ok"] is True
        r = client.post("/settings/test", follow_redirects=True)
        assert "Mock mode" in r.text
