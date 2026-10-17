#!/usr/bin/env sh
# Lance Social Poster sur macOS / Linux.
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Première installation, ça peut prendre une minute..."
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
exec .venv/bin/python app.py
