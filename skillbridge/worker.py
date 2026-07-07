"""Background worker (PRD N3/N4): pulls jobs from the SQLite queue so the UI
never blocks, reports progress in words (F16), and survives reboots — jobs
left 'running' are re-queued at startup.
"""

import json
import threading
import time
import traceback

from . import config, db
from .apply import atomic_write, registry_append
from .classifier import CLAUDE_ONLY, classify
from .diffing import diff_method_cores
from .extractor import extract_method_core
from .parser import SkillParseError, parse_skill_folder
from .translators import KINDS, generate_artefact

KIND_LABELS = {
    "hermes": "standing rule",
    "obsidian": "Obsidian template",
    "promptpack": "Qwen prompt pack",
}


def _progress(job_id: int, text: str) -> None:
    db.update_job(job_id, progress=text)


def _confidential_hits(text: str) -> list[str]:
    cfg = config.load_config()
    return [kw for kw in cfg.get("confidential_keywords", [])
            if kw and kw.lower() in text.lower()]


def run_port_job(job) -> None:
    skill_id = job["skill_id"]
    row = db.get_skill(skill_id)
    _progress(job["id"], "Reading skill…")
    try:
        skill = parse_skill_folder(row["source_dir"])
    except SkillParseError as e:
        db.update_skill(skill_id, status="error", error=str(e))
        return

    hits = _confidential_hits(skill.body)
    if hits:
        db.update_skill(
            skill_id, status="halted",
            error=(
                "This skill mentions flagged confidential terms "
                f"({', '.join(hits)}) and was halted without porting (your rule)."
            ),
        )
        return

    _progress(job["id"], "Classifying portability…")
    cls = classify(skill)
    reasoning = cls.reasoning + (f"\n\n{cls.llm_note}" if cls.llm_note else "")
    db.update_skill(
        skill_id,
        verdict=cls.verdict,
        verdict_reasoning=reasoning,
        claude_only_items=json.dumps(cls.claude_only_items),
    )

    if cls.verdict == CLAUDE_ONLY:
        registry_append(skill.name, row["version"], cls.verdict, [], status="Run on Claude tier")
        db.update_skill(skill_id, status="claude-only")
        return

    _progress(job["id"], "Extracting the method…")
    core = extract_method_core(skill, cls)
    core_json = json.dumps(core, indent=2)
    # Audit copy of the intermediate JSON next to the skill source (PRD F9).
    atomic_write(config.work_dir() / f"method-core-{skill.name}-v{row['version']}.json", core_json)

    diff = ""
    prev = db.previous_skill(skill.name, row["version"])
    if prev and prev["method_core"]:
        _progress(job["id"], "Comparing with the previous version…")
        diff = diff_method_cores(json.loads(prev["method_core"]), core)
    db.update_skill(skill_id, method_core=core_json, diff_summary=diff)

    for i, kind in enumerate(KINDS, 1):
        _progress(job["id"], f"Drafting {KIND_LABELS[kind]} ({i} of {len(KINDS)})…")
        text, note = generate_artefact(
            kind, core, version=row["version"], portability=cls.verdict
        )
        db.upsert_artefact(skill_id, kind, text)

    registry_append(
        skill.name, row["version"], cls.verdict,
        ["standing rule", "template", "prompt pack"], status="Drafted",
    )
    db.update_skill(skill_id, status="ready")
    _progress(job["id"], "Drafts ready for your review.")


def run_regenerate_job(job) -> None:
    payload = json.loads(job["payload"])
    kind, steering = payload["kind"], payload.get("steering", "")
    skill_id = job["skill_id"]
    row = db.get_skill(skill_id)
    _progress(job["id"], f"Redrafting the {KIND_LABELS[kind]}…")
    core = json.loads(row["method_core"])
    text, note = generate_artefact(
        kind, core, version=row["version"], portability=row["verdict"], steering=steering
    )
    db.upsert_artefact(skill_id, kind, text)
    _progress(job["id"], f"New {KIND_LABELS[kind]} draft ready. {note}")


ACTIONS = {"port": run_port_job, "regenerate": run_regenerate_job}


def process_one_job() -> bool:
    """Run the next queued job. Returns False when the queue is empty."""
    job = db.next_queued_job()
    if job is None:
        return False
    db.update_job(job["id"], status="running")
    try:
        ACTIONS[job["action"]](job)
        db.update_job(job["id"], status="done")
    except Exception as e:
        db.update_job(job["id"], status="error", progress=f"Something went wrong: {e}")
        db.update_skill(job["skill_id"], status="error",
                        error=f"{e}\n{traceback.format_exc(limit=3)}")
    return True


def drain_queue() -> None:
    """Process every queued job now (used by tests and the CLI)."""
    while process_one_job():
        pass


class Worker(threading.Thread):
    def __init__(self, poll_interval: float = 0.5):
        super().__init__(daemon=True, name="skillbridge-worker")
        self.poll_interval = poll_interval
        self.stop_event = threading.Event()

    def run(self):
        db.requeue_interrupted_jobs()
        while not self.stop_event.is_set():
            try:
                if not process_one_job():
                    time.sleep(self.poll_interval)
            except Exception:
                time.sleep(self.poll_interval)
