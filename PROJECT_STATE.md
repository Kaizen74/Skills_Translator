# Project State
*Last updated: 2026-07-07 — update after EVERY increment*

## What this project is
SkillBridge: a fully-local web app for the Beelink GTR9 Pro (Ubuntu) that translates Claude SKILL.md skill folders into three reusable local artefacts — a Hermes standing rule, an Obsidian template, and a Qwen prompt pack — using the local Ollama LLM only. The owner reviews and approves every artefact in the browser before anything is written. It ports the method, never the file.

## Current status
v1 complete: ingestion, classification, method-core extraction, three translators, review/approve UI, registry, re-port diffing, install script, systemd service, full test suite (mock LLM mode).

## This session
- [x] Increment 1 — Scaffold: state files, run_checks.sh, requirements, .gitignore
- [x] Increment 2 — Core package: config, database, skill parser + fixtures + tests
- [x] Increment 3 — Classifier (rules + LLM confirm), LLM client (Ollama + mock), method-core extractor + tests
- [x] Increment 4 — Three translators + validators (incl. human-only field enforcement) + tests
- [x] Increment 5 — Apply logic (atomic writes, no-overwrite), registry, re-port diffing + tests
- [x] Increment 6 — Background worker, inbox watcher, FastAPI app + browser UI, end-to-end mock test
- [x] Increment 7 — install.sh, systemd user service, health checks, no-egress test
- [x] Increment 8 — README (non-technical deployment guide), GUIDE.md, final green run

## Done (all sessions)
- 2026-07-07 Full SkillBridge v1 pipeline built and tested in mock-LLM mode.

## Not started yet
- Live-LLM verification on the actual Beelink (needs the real machine: `ollama list` to confirm the model tag).
- v2 candidates (out of scope for v1): direct Hermes config writes, two-way sync.

## How to resume (write this as if for a stranger)
1. The next task is: run the app on the real Beelink, confirm the Ollama model tag in Settings, and do one live-LLM port of a real skill (e.g. pkm-processor).
2. The relevant files are: `skillbridge/` (app code), `tests/` (suite), `install.sh` (deployment), `README.md` (owner instructions).
3. Watch out for: the Ollama model tag default is `qwen3.5:35b-a3b` — the PRD says to verify with `ollama list`, never guess. Change it in the Settings screen if it differs.
4. Run `./run_checks.sh` first — all should pass (mock mode; no model needed).

## Known issues
- Live-LLM mode is implemented but has only been exercised via mocked HTTP in tests — a live pass on the real machine is the remaining acceptance step.
