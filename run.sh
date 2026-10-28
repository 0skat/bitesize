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

# Keep an existing venv's dependencies current with requirements.txt. Cheap
# when nothing changed, and it stops a stale venv failing on a new import.
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

# Run. Always through the venv interpreter — a bare `python dashboard.py` picks
# up the system install, which has no project dependencies.
case "${1:-digest}" in
  dashboard)
    exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/dashboard.py"
    ;;
  digest)
    shift 2>/dev/null || true
    exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py" "$@"
    ;;
  *)
    exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py" "$@"
    ;;
esac
