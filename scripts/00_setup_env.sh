#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
sudo apt-get update -y && sudo apt-get install -y python3 python3-venv python3-pip curl wget md5sum 2>/dev/null || true
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 --version | tee outputs/env_report.txt
pip freeze >> outputs/env_report.txt
echo "Setup complete. Activate with: source .venv/bin/activate"
