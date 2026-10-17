#!/usr/bin/env sh
# Starts Social Poster on macOS / Linux.
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "First-time setup, this may take a minute..."
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
exec .venv/bin/python app.py
