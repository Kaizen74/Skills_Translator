import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets its own SkillBridge home + vault, and mock LLM mode."""
    home = tmp_path / "SkillBridge"
    vault = tmp_path / "Vault"
    for sub in ("00-Inbox", "Concepts", "People", "Ventures", "Crossovers", "Reading", "Synthesis"):
        (vault / sub).mkdir(parents=True)
    monkeypatch.setenv("SKILLBRIDGE_HOME", str(home))
    monkeypatch.setenv("SKILLBRIDGE_MOCK_LLM", "1")

    from skillbridge import config, db
    config.ensure_dirs()
    cfg = config.load_config()
    cfg["vault_path"] = str(vault)
    config.save_config(cfg)
    # Reset any thread-local DB connection from a previous test's home dir.
    if hasattr(db._local, "conn"):
        db._local.conn.close()
        del db._local.conn
    yield {"home": home, "vault": vault}


@pytest.fixture
def fixture_skill(tmp_path):
    """Copy a named fixture skill into a scratch dir (tests may mutate it)."""
    def _copy(name: str) -> Path:
        dest = tmp_path / "skills" / name
        shutil.copytree(FIXTURES / name, dest)
        return dest
    return _copy
