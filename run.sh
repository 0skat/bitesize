#!/bin/bash
# BiteSIze launcher — sets up a virtual environment on first run, then starts the digest.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# Create venv if it doesn't exist yet
if [ ! -d "$VENV_DIR" ]; then
  echo "Setting up virtual environment (first run only)..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
  echo "Done! Starting BiteSIze..."
  echo ""
fi

# Run
"$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py"
