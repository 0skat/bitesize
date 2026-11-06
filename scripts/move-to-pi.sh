#!/usr/bin/env bash
# Move BiteSIze from this Mac to an always-on Linux box (a Raspberry Pi) on
# your tailnet, so the dashboard and the 06:50 run no longer depend on the
# laptop being awake.
#
#   scripts/move-to-pi.sh you@pi-home [--with-google]
#
# Run on the Mac. The Pi must already be prepared (SSH key login, Tailscale up,
# python3-venv and rsync installed) — see ~/dev/hybrid-tracker/pi/prepare.sh.
#
# What it does, in order:
#   1. checks the Pi
#   2. stops the Mac LaunchAgents so nothing writes mid-copy
#   3. copies the repo, data/, output/ and .env to ~/bitesize on the Pi
#      (token.json / credentials.json only with --with-google)
#   4. on the Pi: rewrites stored EPUB paths, turns iCloud Books delivery off
#      (it is macOS-only; the dashboard's Download EPUB replaces it), builds
#      .venv, runs the test suite, installs the claude CLI if missing,
#      installs the systemd units and runs `tailscale serve` on 443
#   5. checks the Pi answers over HTTPS, then turns off the Mac's 443 mapping
#
# The Mac copy is left in place, only stopped. Nothing is deleted.
set -euo pipefail

HOST="${1:-}"
WITH_GOOGLE=0
[[ "${2:-}" == "--with-google" ]] && WITH_GOOGLE=1
if [[ -z "${HOST}" || "${HOST}" == -* ]]; then
  sed -n '6,8p' "$0" >&2
  exit 1
fi
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "error: run this on the Mac that has BiteSIze now." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="$(sed -n 's/^PORT *= *\([0-9]\{1,\}\).*/\1/p' "${ROOT}/dashboard.py" | head -1)"
PORT="${PORT:-8765}"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}")

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

mac_tailscale() {
  if command -v tailscale >/dev/null 2>&1; then echo tailscale
  elif [[ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]]; then
    echo /Applications/Tailscale.app/Contents/MacOS/Tailscale
  fi
}

# ── 1. Preflight ────────────────────────────────────────────────────────────
say "1/5  Checking ${HOST}"
if ! "${SSH[@]}" true 2>/dev/null; then
  echo "error: can't SSH to ${HOST} with a key. Run pi/prepare.sh from hybrid-tracker first." >&2
  exit 1
fi
"${SSH[@]}" 'set -e
  python3 -c "import sys; assert sys.version_info >= (3, 11), sys.version" \
    || { echo "Python 3.11+ needed on the Pi"; exit 1; }
  python3 -c "import venv, ensurepip" 2>/dev/null \
    || { echo "python3-venv missing: sudo apt install python3-venv"; exit 1; }
  command -v rsync >/dev/null || { echo "rsync missing: sudo apt install rsync"; exit 1; }
  command -v tailscale >/dev/null || { echo "Tailscale not installed on the Pi"; exit 1; }
  echo "  Pi: $(python3 --version), $(uname -m), $(free -m | awk "/Mem:/{print \$2}") MB RAM"'
REMOTE_HOME="$("${SSH[@]}" 'printf %s "$HOME"')"
# Pi-hole (or anything else) may already own 443 on the Pi; tailscale serve
# can't share it. Fall back to 8444 so Hybrid Log keeps 8443.
HTTPS_PORT=443
if "${SSH[@]}" "ss -ltnH 'sport = :443' | grep -q ."; then
  HTTPS_PORT=8444
  echo "  port 443 is taken on the Pi (Pi-hole?); BiteSIze will use https port ${HTTPS_PORT}"
fi
REMOTE_ROOT="${REMOTE_HOME}/bitesize"

# If anything below fails, say how to get the Mac copy back.
restore_hint() {
  echo >&2
  echo "Stopped part way. The Mac copy is untouched; to run it again here:" >&2
  echo "  launchctl load -w ~/Library/LaunchAgents/com.bitesize.dashboard.plist" >&2
  echo "  launchctl load -w ~/Library/LaunchAgents/com.bitesize.digest.plist" >&2
}
trap 'restore_hint' ERR

# ── 2. Stop the Mac side ────────────────────────────────────────────────────
say "2/5  Stopping BiteSIze on this Mac"
for label in com.bitesize.dashboard com.bitesize.digest; do
  plist="${HOME}/Library/LaunchAgents/${label}.plist"
  if [[ -f "${plist}" ]]; then
    launchctl unload -w "${plist}" 2>/dev/null || true
    echo "  unloaded ${label} (plist kept; 'launchctl load -w ${plist}' undoes this)"
  fi
done
pkill -f "${ROOT}/dashboard.py" 2>/dev/null || true

# ── 3. Copy ─────────────────────────────────────────────────────────────────
say "3/5  Copying to ${HOST}:${REMOTE_ROOT}"
EXCLUDES=(--exclude .venv --exclude __pycache__ --exclude .pytest_cache
          --exclude 'wordflow/node_modules' --exclude 'wordflow/.next'
          --exclude 'output/logs' --exclude .DS_Store)
if [[ "${WITH_GOOGLE}" -eq 0 ]]; then
  # Gmail and Calendar are off; don't put a live Google token on a new box.
  EXCLUDES+=(--exclude /token.json --exclude /credentials.json)
fi
"${SSH[@]}" "mkdir -p '${REMOTE_ROOT}'"
rsync -a "${EXCLUDES[@]}" -e "ssh -o BatchMode=yes" "${ROOT}/" "${HOST}:${REMOTE_ROOT}/"
"${SSH[@]}" "chmod 700 '${REMOTE_ROOT}/data'; chmod 600 '${REMOTE_ROOT}'/data/* '${REMOTE_ROOT}/.env' 2>/dev/null || true"

# ── 4. Set up on the Pi ─────────────────────────────────────────────────────
say "4/5  Setting up on the Pi (sudo will ask for your Pi password once)"
ssh -t "${HOST}" "set -eo pipefail; cd '${REMOTE_ROOT}'
  python3 - <<'PY'
import sqlite3
from pathlib import Path
root = Path.cwd()
con = sqlite3.connect(root / 'data' / 'bitesize.db')
rows = con.execute('SELECT id, epub_path FROM issues').fetchall()
for iid, p in rows:
    con.execute('UPDATE issues SET epub_path = ? WHERE id = ?',
                (str(root / 'output' / Path(p).name), iid))
con.execute(\"UPDATE settings SET value = '0' WHERE key = 'books_delivery_enabled'\")
con.commit()
print(f'  rewrote {len(rows)} stored EPUB paths; iCloud Books delivery off')
PY
  if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt -r requirements-dev.txt
  echo '  running the test suite...'
  .venv/bin/python -m pytest tests/ -q -p no:cacheprovider
  if [ ! -x \"\$HOME/.local/bin/claude\" ]; then
    echo '  installing the claude CLI (the AI backend)...'
    curl -fsSL https://claude.ai/install.sh | bash
  fi
  bash scripts/install-linux-systemd.sh
  tailscale serve --bg --https=${HTTPS_PORT} ${PORT} || sudo tailscale serve --bg --https=${HTTPS_PORT} ${PORT}
"

# ── 5. Verify, then retire the Mac's tailnet mapping ────────────────────────
say "5/5  Checking the Pi answers over HTTPS"
DNS="$("${SSH[@]}" "tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"Self\"][\"DNSName\"].rstrip(\".\"))'")"
URL="https://${DNS}"
[[ "${HTTPS_PORT}" != 443 ]] && URL="${URL}:${HTTPS_PORT}"
ok=0
for _ in 1 2 3 4 5 6; do
  if curl -fsS --max-time 10 "${URL}/api/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 5
done
if [[ "${ok}" -ne 1 ]]; then
  trap - ERR
  echo "warning: ${URL}/api/health didn't answer yet. The Mac's mapping is left on." >&2
  echo "  On the Pi: systemctl status bitesize-dashboard; tailscale serve status" >&2
  exit 1
fi
trap - ERR
TS="$(mac_tailscale)"
if [[ -n "${TS}" ]]; then
  "${TS}" serve --https=443 off 2>/dev/null && echo "  turned off this Mac's 443 mapping" || true
fi

cat <<EOF

BiteSIze now runs on the Pi:
  Dashboard:  ${URL}
  Daily pool: 06:50 Pi time (systemd timer, catches up after power cuts)

One thing left — log the claude CLI in on the Pi, once:
  ssh -t ${HOST} '~/.local/bin/claude'     # follow the login link, then /exit

Test a run any time:  ssh -t ${HOST} 'sudo systemctl start bitesize-digest'
On the phone: open ${URL}, Issue tab, Download EPUB, then Open in Books.
EOF
