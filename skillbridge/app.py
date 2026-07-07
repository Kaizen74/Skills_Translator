"""The SkillBridge web app (PRD §6.4/§6.5): FastAPI + Jinja2 + vanilla JS.

Single-user, fully local. Binds to 0.0.0.0 so the owner can reach it over
Tailscale from the laptop (PRD F14); it still never makes outbound calls.
"""

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import config, db
from .apply import apply_obsidian, apply_promptpack, registry_read, registry_update_status
from .ingest import IngestError, InboxWatcher, ingest_upload
from .llm import get_llm
from .worker import KIND_LABELS, Worker

_worker: Worker | None = None
_watcher: InboxWatcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker, _watcher
    config.ensure_dirs()
    db.requeue_interrupted_jobs()
    _worker = Worker()
    _worker.start()
    _watcher = InboxWatcher()
    _watcher.start()
    yield
    _worker.stop_event.set()
    _watcher.stop_event.set()


app = FastAPI(title="SkillBridge", lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def health() -> dict:
    cfg = config.load_config()
    ok, ollama_msg = get_llm(cfg).ping()
    vault = config.vault_path(cfg)
    vault_ok = vault.is_dir()
    try:
        free_gb = shutil.disk_usage(str(config.home_dir())).free / 1e9
    except OSError:
        free_gb = 0.0
    return {
        "ollama_ok": ok,
        "ollama_msg": ollama_msg,
        "vault_ok": vault_ok,
        "vault_msg": (
            f"Vault found at {vault}." if vault_ok
            else f"Vault folder not found at {vault} — check Settings."
        ),
        "disk_ok": free_gb > 2,
        "disk_msg": f"{free_gb:.0f} GB of disk space free.",
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request, error: str = ""):
    skills = db.list_skills()
    jobs = {s["id"]: db.latest_job_for_skill(s["id"]) for s in skills}
    return templates.TemplateResponse(request, "home.html", {
        "skills": skills, "jobs": jobs, "health": health(),
        "inbox_dir": str(config.inbox_dir()), "error": error,
    })


@app.post("/upload")
async def upload(file: UploadFile):
    data = await file.read()
    try:
        ingest_upload(data, file.filename or "skill.zip")
    except IngestError as e:
        return RedirectResponse(url=f"/?error={e}", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@app.get("/skill/{skill_id}", response_class=HTMLResponse)
def review(request: Request, skill_id: int):
    skill = db.get_skill(skill_id)
    if skill is None:
        return RedirectResponse(url="/", status_code=303)
    artefacts = {a["kind"]: a for a in db.get_artefacts(skill_id)}
    job = db.latest_job_for_skill(skill_id)
    return templates.TemplateResponse(request, "review.html", {
        "skill": skill, "artefacts": artefacts, "job": job,
        "kind_labels": KIND_LABELS,
        "claude_only_items": json.loads(skill["claude_only_items"] or "[]"),
        "vault_dir": str(config.vault_path()),
    })


@app.post("/skill/{skill_id}/approve/{kind}")
def approve(skill_id: int, kind: str, content: str = Form(...), dest_dir: str = Form("")):
    skill = db.get_skill(skill_id)
    art = db.get_artefact(skill_id, kind)
    if skill is None or art is None:
        return RedirectResponse(url="/", status_code=303)
    if kind == "obsidian":
        path, msg = apply_obsidian(skill["name"], content, dest_dir or None)
        db.update_artefact(art["id"], content=content, status="approved", applied_path=str(path))
    elif kind == "promptpack":
        path, msg = apply_promptpack(skill["name"], content)
        db.update_artefact(art["id"], content=content, status="approved", applied_path=str(path))
    else:  # hermes: nothing is written anywhere — it becomes copy-ready (PRD F11)
        db.update_artefact(art["id"], content=content, status="approved")
    registry_update_status(skill["name"], skill["version"], "Approved")
    _maybe_mark_done(skill_id)
    return RedirectResponse(url=f"/skill/{skill_id}", status_code=303)


@app.post("/skill/{skill_id}/skip/{kind}")
def skip(skill_id: int, kind: str):
    art = db.get_artefact(skill_id, kind)
    if art:
        db.update_artefact(art["id"], status="skipped")
    _maybe_mark_done(skill_id)
    return RedirectResponse(url=f"/skill/{skill_id}", status_code=303)


@app.post("/skill/{skill_id}/regenerate/{kind}")
def regenerate(skill_id: int, kind: str, steering: str = Form("")):
    db.enqueue_job(skill_id, "regenerate", {"kind": kind, "steering": steering})
    return RedirectResponse(url=f"/skill/{skill_id}", status_code=303)


@app.post("/skill/{skill_id}/rule-sent")
def rule_sent(skill_id: int):
    skill = db.get_skill(skill_id)
    if skill:
        registry_update_status(skill["name"], skill["version"], "Rule sent")
    return RedirectResponse(url=f"/skill/{skill_id}", status_code=303)


def _maybe_mark_done(skill_id: int) -> None:
    arts = db.get_artefacts(skill_id)
    if arts and all(a["status"] in ("approved", "skipped") for a in arts):
        db.update_skill(skill_id, status="done")


@app.get("/api/skill/{skill_id}/status")
def skill_status(skill_id: int):
    skill = db.get_skill(skill_id)
    if skill is None:
        return JSONResponse({"error": "unknown skill"}, status_code=404)
    job = db.latest_job_for_skill(skill_id)
    return {
        "status": skill["status"],
        "progress": job["progress"] if job else "",
        "job_status": job["status"] if job else "",
    }


@app.get("/registry", response_class=HTMLResponse)
def registry_view(request: Request):
    md = registry_read()
    rows = []
    for line in md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0] != "Skill" and not set(cells[0]) <= {"-"}:
            rows.append(cells)
    return templates.TemplateResponse(request, "registry.html", {
        "rows": rows, "registry_path": str(config.registry_path()),
    })


@app.get("/settings", response_class=HTMLResponse)
def settings_view(request: Request, saved: str = "", test_result: str = ""):
    return templates.TemplateResponse(request, "settings.html", {
        "cfg": config.load_config(), "saved": saved, "test_result": test_result,
        "mock": config.mock_llm(),
    })


@app.post("/settings")
def settings_save(vault_path: str = Form(...), model_tag: str = Form(...),
                  port: int = Form(...), ollama_url: str = Form(...)):
    cfg = config.load_config()
    cfg.update({
        "vault_path": vault_path.strip(), "model_tag": model_tag.strip(),
        "port": port, "ollama_url": ollama_url.strip(),
    })
    config.save_config(cfg)
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@app.post("/settings/test")
def settings_test():
    ok, msg = get_llm().ping()
    prefix = "✅ " if ok else "⚠️ "
    return RedirectResponse(url=f"/settings?test_result={prefix}{msg}", status_code=303)


@app.get("/api/health")
def api_health():
    return health()


def _setup_logging():
    """Rotating file log (PRD F19)."""
    import logging
    from logging.handlers import RotatingFileHandler

    config.ensure_dirs()
    handler = RotatingFileHandler(
        config.log_dir() / "skillbridge.log", maxBytes=2_000_000, backupCount=5
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def main():
    """Entry point used by the systemd service."""
    import uvicorn
    _setup_logging()
    cfg = config.load_config()
    uvicorn.run(app, host="0.0.0.0", port=int(cfg["port"]))


if __name__ == "__main__":
    main()
