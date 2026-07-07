"""PRD N5: the runtime code makes no HTTP calls to non-localhost hosts.
Scans every source file of the app package for URLs and network imports."""

import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "skillbridge"

CLOUD_CLIENT_IMPORTS = re.compile(
    r"^\s*(import|from)\s+(requests|httpx|aiohttp|openai|anthropic|boto3)\b", re.MULTILINE
)


def test_all_urls_in_runtime_code_are_localhost():
    for py in PKG.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for url in re.findall(r"https?://[^\s\"')]+", text):
            host = re.sub(r"https?://", "", url).split("/")[0].split(":")[0]
            assert host in ("127.0.0.1", "localhost", "::1"), (
                f"{py.name} references a non-local URL: {url}"
            )


def test_no_cloud_http_client_imports_in_runtime_code():
    for py in PKG.rglob("*.py"):
        m = CLOUD_CLIENT_IMPORTS.search(py.read_text(encoding="utf-8"))
        assert m is None, f"{py.name} imports a network client: {m.group(0).strip()}"


def test_llm_refuses_non_localhost_url(isolated_env, monkeypatch):
    monkeypatch.setenv("SKILLBRIDGE_MOCK_LLM", "0")
    import pytest
    from skillbridge.llm import LLMError, OllamaClient
    cfg = {"ollama_url": "http://api.example.com", "model_tag": "x"}
    with pytest.raises(LLMError, match="only ever talks to the local"):
        OllamaClient(cfg)
