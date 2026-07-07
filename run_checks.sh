#!/bin/bash
# run_checks.sh — run everything; exit non-zero on any failure
set -e
cd "$(dirname "$0")"

PY="${SKILLBRIDGE_PY:-python3}"
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; fi

echo "1/3 Syntax check (compiling every Python file)..."
"$PY" -m compileall -q -x 'fixtures' skillbridge tests

echo "2/3 Automated tests (mock LLM mode — no model needed)..."
SKILLBRIDGE_MOCK_LLM=1 "$PY" -m pytest tests -q

echo "3/3 Smoke test (start the app, load the home screen)..."
SKILLBRIDGE_MOCK_LLM=1 "$PY" -m pytest tests/test_e2e_mock.py -q

echo "ALL CHECKS PASSED ✅"
