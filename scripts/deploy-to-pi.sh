#!/usr/bin/env bash
# Run ON THE MAC. Ship BiteSIze code changes to the Pi, safely. (Twin of
# ~/dev/hybrid-tracker/pi/deploy.sh; only the settings block differs.)
#
#   scripts/deploy-to-pi.sh                          # the Pi you deployed to last time
#   scripts/deploy-to-pi.sh sodanetwork@100.83.85.62
#
#   1. lists the code to ship (never data/, logs/, backups, .venv, secrets)
#   2. unpacks it into an empty staging folder on the Pi
#   3. snapshots the code that's live now, then syncs staging into place
#   4. installs requirements and runs the test suite ON THE PI
#   5. restarts the service and checks its health URL
#   6. if 4 or 5 fails, puts the snapshot back and restarts that instead
#
# Live data on the Pi is never in the shipment and is excluded from the sync,
# so a deploy can't overwrite or delete it. The first deploy asks for your Pi
# password once, to allow restarting this one service without a password.
set -euo pipefail

# ── per-app settings ────────────────────────────────────────────────────────
APP="bitesize"                             # folder under ~ on the Pi
SERVICE="bitesize-dashboard"               # systemd unit to restart (the 06:50 timer needs none)
HEALTH="http://127.0.0.1:8765/api/health"
TEST_CMD=".venv/bin/python -m pytest tests/ -q -p no:cacheprovider"
INSTALL_CMD=".venv/bin/pip install --quiet -r requirements.txt -r requirements-dev.txt"
LOG_CMD="tail -n 15 output/logs/dashboard-stderr.log"  # shown if the restart fails
# Top-level paths that live only on the Pi (or only on the Mac). Never shipped,
# never touched on the Pi: the settings DB, EPUBs, secrets, Google tokens.
KEEP=(data output .env token.json credentials.json .venv .git wordflow)
# ────────────────────────────────────────────────────────────────────────────

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_FILE="${HOME}/.config/pi-deploy-host"
HOST="${1:-$(cat "${HOST_FILE}" 2>/dev/null || true)}"
if [[ -z "${HOST}" ]]; then
  echo "usage: $(basename "$0") you@pi   (remembered after the first time)" >&2
  exit 1
fi
mkdir -p "$(dirname "${HOST_FILE}")" && printf '%s\n' "${HOST}" > "${HOST_FILE}"

SSH=(ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}")
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

# Anchored rsync excludes for the Pi side (GNU rsync there).
RSYNC_KEEP=""
for k in "${KEEP[@]}"; do RSYNC_KEEP+=" --exclude '/${k}'"; done
RSYNC_KEEP+=" --exclude __pycache__ --exclude .pytest_cache"

say "Deploying $(basename "${ROOT}") → ${HOST}:~/${APP}"
"${SSH[@]}" "test -x ~/${APP}/.venv/bin/python" || {
  echo "error: ~/${APP} isn't set up on the Pi. Run the move-to-pi script first." >&2; exit 1; }

# ── 1. What ships ───────────────────────────────────────────────────────────
LIST="$(mktemp)"; trap 'rm -f "${LIST}"' EXIT
PRUNE=()
for k in "${KEEP[@]}"; do PRUNE+=(-path "./${k}" -o); done
(cd "${ROOT}" && find . \( "${PRUNE[@]}" -name __pycache__ -o -name .pytest_cache -o -name .DS_Store \) -prune \
   -o -type f -print) | sort > "${LIST}"
for k in "${KEEP[@]}"; do
  if grep -q "^\./${k}/" "${LIST}" 2>/dev/null; then
    echo "error: refusing to ship ${k}/ — the file list is wrong" >&2; exit 1
  fi
done
echo "  $(wc -l < "${LIST}" | tr -d ' ') files"

# One-time: let this user restart this one unit without a password.
if ! "${SSH[@]}" "sudo -n -l /usr/bin/systemctl restart ${SERVICE} >/dev/null 2>&1"; then
  say "One-time setup: allow restarting ${SERVICE} without a password (asks for your Pi password)"
  ssh -t "${HOST}" "set -e
    tmp=\$(mktemp)
    echo \"\$(id -un) ALL=(root) NOPASSWD: /usr/bin/systemctl restart ${SERVICE}\" > \"\$tmp\"
    sudo visudo -cf \"\$tmp\" >/dev/null
    sudo install -m 0440 \"\$tmp\" /etc/sudoers.d/deploy-${SERVICE}
    rm -f \"\$tmp\"; echo '  done'"
fi

# ── 2. Stage ────────────────────────────────────────────────────────────────
say "1/4  Sending to a staging folder on the Pi"
"${SSH[@]}" "rm -rf ~/.deploy/${APP}-incoming && mkdir -p ~/.deploy/${APP}-incoming"
(cd "${ROOT}" && COPYFILE_DISABLE=1 tar --no-xattrs -cf - -T "${LIST}") \
  | "${SSH[@]}" "tar -xf - --warning=no-unknown-keyword -C ~/.deploy/${APP}-incoming"

# ── 3. Snapshot, then swap in ───────────────────────────────────────────────
say "2/4  Snapshot of the live code, then swap in the new code"
"${SSH[@]}" "set -e
  rsync -a --delete ${RSYNC_KEEP} ~/${APP}/ ~/.deploy/${APP}-previous/
  rsync -a --delete --itemize-changes ${RSYNC_KEEP} ~/.deploy/${APP}-incoming/ ~/${APP}/ | grep -v '^\.' | sed 's/^/  /' || true"

rollback() {
  say "Rolling back to the snapshot"
  if "${SSH[@]}" "set -e
      rsync -a --delete ${RSYNC_KEEP} ~/.deploy/${APP}-previous/ ~/${APP}/
      sudo -n /usr/bin/systemctl restart ${SERVICE}
      for i in \$(seq 1 15); do curl -fsS -o /dev/null ${HEALTH} && exit 0; sleep 1; done; exit 1"; then
    echo "  the previous version is running again; nothing changed for your phone"
  else
    echo "  rollback needs a hand: ssh ${HOST}, then: systemctl status ${SERVICE}" >&2
  fi
  exit 1
}

# ── 4. Test on the Pi ───────────────────────────────────────────────────────
say "3/4  Requirements and tests on the Pi"
if ! "${SSH[@]}" "cd ~/${APP} && ${INSTALL_CMD} && ${TEST_CMD} 2>&1 | tail -4; exit \${PIPESTATUS[0]}"; then
  echo "  tests failed on the Pi" >&2
  rollback
fi

# ── 5. Restart and check ────────────────────────────────────────────────────
say "4/4  Restarting ${SERVICE}"
if ! "${SSH[@]}" "sudo -n /usr/bin/systemctl restart ${SERVICE}
    for i in \$(seq 1 15); do curl -fsS -o /dev/null ${HEALTH} && exit 0; sleep 1; done; exit 1"; then
  echo "  ${SERVICE} didn't come back healthy. Last log lines:" >&2
  "${SSH[@]}" "cd ~/${APP} && ${LOG_CMD}" 2>/dev/null | sed 's/^/  /' || true
  rollback
fi

echo
echo "Deployed. ${SERVICE} is healthy on ${HOST}."
