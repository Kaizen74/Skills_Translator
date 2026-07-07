"""LLM access. Two implementations behind one interface:

- OllamaClient: calls the local Ollama HTTP API. The URL is asserted to be
  localhost — SkillBridge never makes a network call to any other host (PRD N5).
- MockLLM: deterministic outputs derived from the request context, so the whole
  pipeline and UI run with zero model load (PRD N1).

Selection: SKILLBRIDGE_MOCK_LLM=1 -> MockLLM, otherwise OllamaClient.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import config

LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LLMError(Exception):
    """Plain-language LLM failure, safe to show in the UI."""


def _assert_localhost(url: str) -> None:
    host = urllib.parse.urlparse(url).hostname or ""
    if host not in LOCALHOST_HOSTS:
        raise LLMError(
            f"Refusing to contact '{host}': SkillBridge only ever talks to the "
            "local Ollama on this machine. Check the Ollama URL in Settings."
        )


class OllamaClient:
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or config.load_config()
        self.base_url = cfg["ollama_url"].rstrip("/")
        self.model = cfg["model_tag"]
        _assert_localhost(self.base_url)

    def generate(self, prompt: str, system: str = "", as_json: bool = False) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if as_json:
            payload["format"] = "json"
        req = urllib.request.Request(
            self.base_url + "/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise LLMError(
                "Could not reach the local AI model (Ollama). Is Ollama running? "
                f"Technical detail: {e.reason if hasattr(e, 'reason') else e}"
            )
        return data.get("response", "")

    def ping(self) -> tuple[bool, str]:
        """Plain-language connection test for the Settings screen."""
        try:
            req = urllib.request.Request(self.base_url + "/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tags = [m.get("name", "") for m in data.get("models", [])]
            if self.model in tags:
                return True, f"Connected. The model '{self.model}' is installed and ready."
            return False, (
                f"Ollama is running, but the model '{self.model}' is not installed. "
                f"Models found: {', '.join(tags) or 'none'}. Fix the model name in "
                "Settings to match one of these."
            )
        except (urllib.error.URLError, OSError) as e:
            return False, (
                "Could not reach Ollama on this machine. It may not be running. "
                f"Technical detail: {e}"
            )


class MockLLM:
    """Deterministic stand-in. Produces stable, valid-shaped answers from the
    prompt text itself, so tests and UI demos need no model."""

    model = "mock"

    def generate(self, prompt: str, system: str = "", as_json: bool = False) -> str:
        if as_json:
            # The extractor embeds the payload it wants confirmed between
            # sentinel markers; echo a deterministic derivation of it.
            m = re.search(r"<<INPUT>>(.*?)<<END>>", prompt, re.DOTALL)
            if m:
                return m.group(1).strip()
            return "{}"
        m = re.search(r"<<INPUT>>(.*?)<<END>>", prompt, re.DOTALL)
        return (m.group(1).strip() if m else "MOCK RESPONSE")

    def ping(self) -> tuple[bool, str]:
        return True, "Mock mode is on — no model is used."


def get_llm(cfg: dict | None = None):
    if config.mock_llm():
        return MockLLM()
    return OllamaClient(cfg)
