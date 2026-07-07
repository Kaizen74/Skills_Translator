# Decisions Log
| Date | Decision | Why | Alternative rejected |
|---|---|---|---|
| 2026-07-07 | FastAPI + Jinja2 templates + vanilla JS, no build toolchain | PRD F14: boring, repairable stack; no npm | React/Vite (build chain a non-technical owner can't repair) |
| 2026-07-07 | SQLite single file in ~/SkillBridge/ for all state | PRD F18; zero admin, survives reboot | Postgres (needs a server) |
| 2026-07-07 | LLM calls via Ollama HTTP API on 127.0.0.1 only, stdlib urllib | PRD N5 zero egress; one less dependency in the runtime path | OpenAI-compatible clients (pull in cloud-shaped config) |
| 2026-07-07 | Mock LLM is deterministic, built from the parsed skill itself | Whole pipeline + UI testable with zero model load (PRD N1) and works for ANY fixture, not just 3 canned ones | Static canned strings (break as soon as a new fixture is added) |
| 2026-07-07 | Human-only fields detected by deterministic regex on the SOURCE skill, not by the LLM | PRD principle 5 is a hard guarantee; can't rest on model behaviour | Trusting the LLM to preserve the field |
| 2026-07-07 | Background work runs in a single worker thread with a SQLite-backed queue | Simple, resumable after reboot (jobs re-queued at startup), UI stays responsive (PRD N3/N4) | Celery/Redis (external services violate the boring-stack rule) |
| 2026-07-07 | Inbox watcher polls every 5s with stdlib | No inotify dependency; 5s is imperceptible for this workflow | watchdog library (extra dep for no user-visible gain) |
| 2026-07-07 | Vault/registry writes: write temp file then os.replace (atomic), never overwrite (auto _v2 suffix) | PRD F11/N4: no corrupted or clobbered vault files, ever | In-place writes |
| 2026-07-07 | systemd **user** service (not system) | Runs as the owner, owns ~/SkillBridge and the vault; starts on boot with lingering enabled | System service (root-owned files in the vault) |
| 2026-07-07 | Default model tag `qwen3.5:35b-a3b`, editable in Settings with a plain-language Ollama test button | PRD §3 + open question 1: recommended default, owner confirms on the real machine | Hard-coding the tag |
