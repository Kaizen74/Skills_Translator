"""Configuration for SkillBridge.

All state lives under SKILLBRIDGE_HOME (default ~/SkillBridge). A small JSON
config file holds the owner-editable settings (vault path, model tag, port);
everything else is derived. Environment variables override for tests.
"""

import json
import os
from pathlib import Path

DEFAULTS = {
    "vault_path": "~/SecondBrain/Vault",
    "model_tag": "qwen3.5:35b-a3b",
    "secondary_model_tag": "qwen2.5:72b",
    "ollama_url": "http://127.0.0.1:11434",
    "port": 8788,
    # Keyword flags supplied by the owner; skills containing any of these are
    # halted with a warning instead of being ported (PRD §5).
    "confidential_keywords": [],
}


def home_dir() -> Path:
    return Path(os.environ.get("SKILLBRIDGE_HOME", "~/SkillBridge")).expanduser()


def config_path() -> Path:
    return home_dir() / "config.json"


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    path = config_path()
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            # A broken config file must never brick the app; fall back to
            # defaults and let the owner re-save from the Settings screen.
            pass
    return cfg


def save_config(cfg: dict) -> None:
    ensure_dirs()
    path = config_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def vault_path(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    return Path(cfg["vault_path"]).expanduser()


def inbox_dir() -> Path:
    return home_dir() / "inbox"


def work_dir() -> Path:
    return home_dir() / "work"


def library_dir() -> Path:
    return home_dir() / "library" / "prompt-packs"


def log_dir() -> Path:
    return home_dir() / "logs"


def db_path() -> Path:
    return home_dir() / "skillbridge.db"


def registry_path(cfg: dict | None = None) -> Path:
    return vault_path(cfg) / "Synthesis" / "Skill-Porting-Registry.md"


def mock_llm() -> bool:
    return os.environ.get("SKILLBRIDGE_MOCK_LLM", "") == "1"


def ensure_dirs() -> None:
    for d in (home_dir(), inbox_dir(), work_dir(), library_dir(), log_dir()):
        d.mkdir(parents=True, exist_ok=True)
