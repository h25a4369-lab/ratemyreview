#!/usr/bin/env bash
# Rate My Review — start the site on macOS or Linux.
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating the virtual environment..."
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip
  ./.venv/bin/python -m pip install -r requirements.txt
fi

echo "Starting Rate My Review at http://127.0.0.1:8000"
exec ./.venv/bin/python -m uvicorn app.main:app --reload
