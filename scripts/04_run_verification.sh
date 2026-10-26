#!/usr/bin/env bash
# Synthetic unit tests: verification of code correctness ONLY. Never used for results.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
python3 -m pytest -v tests | tee outputs/verification_tests.txt
