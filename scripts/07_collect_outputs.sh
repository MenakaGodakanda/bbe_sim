#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
tar czf bbe_outputs.tar.gz outputs
ls -la outputs; echo "Send me bbe_outputs.tar.gz (or paste the CSV/TXT/JSON contents)."
