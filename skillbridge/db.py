"""SQLite persistence. One file, no external database (PRD F18).

Tables:
  skills    — one row per ingested skill version
  artefacts — the three drafts (hermes / obsidian / promptpack) per skill
  jobs      — background work queue; survives reboot (PRD N4)
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    source_dir TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    error TEXT DEFAULT '',
    verdict TEXT DEFAULT '',
    verdict_reasoning TEXT DEFAULT '',
    claude_only_items TEXT DEFAULT '[]',
    method_core TEXT DEFAULT '',
    diff_summary TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS artefacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL REFERENCES skills(id),
    kind TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    applied_path TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL REFERENCES skills(id),
    action TEXT NOT NULL,
    payload TEXT DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    progress TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    path = str(config.db_path())
    if conn is None or getattr(_local, "path", None) != path:
        config.ensure_dirs()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.commit()
        _local.conn = conn
        _local.path = path
    return conn


# --- skills ---------------------------------------------------------------

def create_skill(name: str, description: str, source_dir: str) -> int:
    conn = get_conn()
    version = 1 + (latest_version(name) or 0)
    cur = conn.execute(
        "INSERT INTO skills (name, description, version, source_dir, ingested_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, description, version, source_dir, now()),
    )
    conn.commit()
    return cur.lastrowid


def latest_version(name: str) -> int | None:
    row = get_conn().execute(
        "SELECT MAX(version) AS v FROM skills WHERE name = ?", (name,)
    ).fetchone()
    return row["v"]


def previous_skill(name: str, before_version: int) -> sqlite3.Row | None:
    return get_conn().execute(
        "SELECT * FROM skills WHERE name = ? AND version < ? ORDER BY version DESC LIMIT 1",
        (name, before_version),
    ).fetchone()


def get_skill(skill_id: int) -> sqlite3.Row | None:
    return get_conn().execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()


def list_skills() -> list[sqlite3.Row]:
    return get_conn().execute("SELECT * FROM skills ORDER BY id DESC").fetchall()


def update_skill(skill_id: int, **fields) -> None:
    conn = get_conn()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE skills SET {sets} WHERE id = ?", (*fields.values(), skill_id))
    conn.commit()


# --- artefacts ------------------------------------------------------------

def upsert_artefact(skill_id: int, kind: str, content: str, status: str = "draft") -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM artefacts WHERE skill_id = ? AND kind = ?", (skill_id, kind)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE artefacts SET content = ?, status = ?, updated_at = ? WHERE id = ?",
            (content, status, now(), row["id"]),
        )
        conn.commit()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO artefacts (skill_id, kind, content, status, updated_at) VALUES (?, ?, ?, ?, ?)",
        (skill_id, kind, content, "draft", now()),
    )
    conn.commit()
    return cur.lastrowid


def get_artefacts(skill_id: int) -> list[sqlite3.Row]:
    return get_conn().execute(
        "SELECT * FROM artefacts WHERE skill_id = ? ORDER BY kind", (skill_id,)
    ).fetchall()


def get_artefact(skill_id: int, kind: str) -> sqlite3.Row | None:
    return get_conn().execute(
        "SELECT * FROM artefacts WHERE skill_id = ? AND kind = ?", (skill_id, kind)
    ).fetchone()


def update_artefact(artefact_id: int, **fields) -> None:
    conn = get_conn()
    fields["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE artefacts SET {sets} WHERE id = ?", (*fields.values(), artefact_id))
    conn.commit()


# --- jobs -----------------------------------------------------------------

def enqueue_job(skill_id: int, action: str, payload: dict | None = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO jobs (skill_id, action, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (skill_id, action, json.dumps(payload or {}), now(), now()),
    )
    conn.commit()
    return cur.lastrowid


def next_queued_job() -> sqlite3.Row | None:
    return get_conn().execute(
        "SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1"
    ).fetchone()


def update_job(job_id: int, **fields) -> None:
    conn = get_conn()
    fields["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", (*fields.values(), job_id))
    conn.commit()


def requeue_interrupted_jobs() -> int:
    """Called at startup: any job left 'running' by a reboot goes back to the queue."""
    conn = get_conn()
    cur = conn.execute(
        "UPDATE jobs SET status = 'queued', progress = 'Restarted after interruption', updated_at = ? "
        "WHERE status = 'running'",
        (now(),),
    )
    conn.commit()
    return cur.rowcount


def latest_job_for_skill(skill_id: int) -> sqlite3.Row | None:
    return get_conn().execute(
        "SELECT * FROM jobs WHERE skill_id = ? ORDER BY id DESC LIMIT 1", (skill_id,)
    ).fetchone()
