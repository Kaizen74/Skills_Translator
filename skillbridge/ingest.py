"""Ingestion (PRD F1): ZIP upload from the browser, or folders/ZIPs dropped
into the watched inbox directory ~/SkillBridge/inbox/.

Uploaded content is only ever read and listed — never executed.
"""

import re
import shutil
import threading
import time
import zipfile
from pathlib import Path

from . import config, db
from .parser import SkillParseError, parse_skill_folder


class IngestError(Exception):
    """Plain-language ingestion failure, safe to show to the owner."""


def _fresh_work_dir(label: str) -> Path:
    config.ensure_dirs()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", label) or "skill"
    base = config.work_dir() / f"{int(time.time() * 1000)}-{safe}"
    base.mkdir(parents=True)
    return base


def extract_zip(data: bytes, filename: str) -> Path:
    """Safely extract an uploaded ZIP into a fresh work directory."""
    dest = _fresh_work_dir(Path(filename).stem)
    tmp_zip = dest / "_upload.zip"
    tmp_zip.write_bytes(data)
    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            for member in zf.namelist():
                target = (dest / member).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise IngestError(
                        "This ZIP contains unsafe file paths and was rejected."
                    )
            zf.extractall(dest)
    except zipfile.BadZipFile:
        raise IngestError(
            "That file doesn't look like a valid ZIP. Please re-download the "
            "skill and upload the .zip file itself."
        )
    finally:
        tmp_zip.unlink(missing_ok=True)
    return dest


def register_skill(folder: Path) -> int:
    """Parse enough to identify the skill, create the DB row, queue the port job."""
    try:
        skill = parse_skill_folder(folder)
    except SkillParseError as e:
        raise IngestError(str(e))
    skill_id = db.create_skill(skill.name, skill.description, skill.source_dir)
    db.enqueue_job(skill_id, "port")
    return skill_id


def ingest_zip_bytes(data: bytes, filename: str) -> int:
    return register_skill(extract_zip(data, filename))


def ingest_inbox_item(item: Path) -> int:
    """Move an inbox folder or ZIP into the work area and register it."""
    if item.suffix.lower() == ".zip":
        skill_id = ingest_zip_bytes(item.read_bytes(), item.name)
        item.unlink()
        return skill_id
    dest = _fresh_work_dir(item.name)
    moved = Path(shutil.move(str(item), str(dest / item.name)))
    return register_skill(moved)


class InboxWatcher(threading.Thread):
    """Polls ~/SkillBridge/inbox every few seconds (PRD F1b)."""

    def __init__(self, interval: float = 5.0):
        super().__init__(daemon=True, name="skillbridge-inbox")
        self.interval = interval
        self.stop_event = threading.Event()

    def scan_once(self) -> list[int]:
        ids = []
        inbox = config.inbox_dir()
        if not inbox.exists():
            return ids
        for item in sorted(inbox.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_dir() or item.suffix.lower() == ".zip":
                if item.is_dir() and _still_being_copied(item):
                    continue
                try:
                    ids.append(ingest_inbox_item(item))
                except IngestError as e:
                    # Leave a plain-language note next to the failed item.
                    reject = inbox / (item.name + ".REJECTED.txt")
                    reject.write_text(str(e), encoding="utf-8")
                    if item.is_dir():
                        shutil.move(str(item), str(inbox / (item.name + ".rejected")))
                    else:
                        item.unlink(missing_ok=True)
        return ids

    def run(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.scan_once()
            except Exception:
                pass  # the watcher must never die; problems surface in the UI


def _still_being_copied(folder: Path, settle_seconds: float = 2.0) -> bool:
    """Skip folders modified in the last couple of seconds — a copy may be in flight."""
    try:
        newest = max((p.stat().st_mtime for p in folder.rglob("*")), default=folder.stat().st_mtime)
    except OSError:
        return True
    return (time.time() - newest) < settle_seconds
