#!/usr/bin/env bash
# Install systemd units that run BiteSIze on an always-on Linux box (a
# Raspberry Pi). The Linux twin of install-dashboard-launchd.sh plus
# install-daily-launchd.sh:
#
#   bitesize-dashboard.service  dashboard.py, started at boot, restarted on exit
#   bitesize-digest.timer       main.py --all --pool every day at 06:50
#
# Unlike launchd on a sleeping Mac, the timer is Persistent: a run missed
# while the box was off happens as soon as it boots, and nothing sleeps
# mid-run, so no caffeinate is needed.
#
# Run as your normal user; it asks for sudo to write the units.
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "error: this is the Linux installer. On macOS use install-dashboard-launchd.sh and install-daily-launchd.sh." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${ROOT}/.venv/bin/python"
RUN_USER="$(id -un)"
RUN_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6)"
UNIT_DIR="/etc/systemd/system"

if [[ ! -x "${VENV_PY}" ]]; then
  echo "error: expected Python at ${VENV_PY}" >&2
  echo "  Create it with: cd \"${ROOT}\" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

PORT="$(sed -n 's/^PORT *= *\([0-9]\{1,\}\).*/\1/p' "${ROOT}/dashboard.py" | head -1)"
PORT="${PORT:-8765}"

mkdir -p "${ROOT}/output/logs" "${ROOT}/data"
chmod 700 "${ROOT}/data"

# A hand-started dashboard would hold the port and crash-loop the service.
if pgrep -u "${RUN_USER}" -f "${ROOT}/dashboard.py" >/dev/null 2>&1; then
  echo "Stopping the dashboard that is already running..."
  pkill -u "${RUN_USER}" -f "${ROOT}/dashboard.py" || true
  sleep 2
fi

# Shared hardening. ProtectHome stays off: the claude CLI keeps its login and
# auto-updates under ~/.claude and ~/.local, and the digest needs both.
read -r -d '' HARDEN <<'EOF' || true
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
UMask=0077
EOF

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

cat > "${TMP}/bitesize-dashboard.service" <<EOF
[Unit]
Description=BiteSIze dashboard (127.0.0.1:${PORT})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${ROOT}
Environment=PYTHONUNBUFFERED=1
Environment=HOME=${RUN_HOME}
ExecStart=${VENV_PY} ${ROOT}/dashboard.py
Restart=always
# If the port is taken it exits at once; don't respawn every second.
RestartSec=30
StandardOutput=append:${ROOT}/output/logs/dashboard-stdout.log
StandardError=append:${ROOT}/output/logs/dashboard-stderr.log
${HARDEN}

[Install]
WantedBy=multi-user.target
EOF

cat > "${TMP}/bitesize-digest.service" <<EOF
[Unit]
Description=BiteSIze daily pool (main.py --all --pool)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=${RUN_USER}
WorkingDirectory=${ROOT}
Environment=PYTHONUNBUFFERED=1
Environment=HOME=${RUN_HOME}
Environment=PATH=${RUN_HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${VENV_PY} ${ROOT}/main.py --all --pool
TimeoutStartSec=3h
StandardOutput=append:${ROOT}/output/logs/digest-stdout.log
StandardError=append:${ROOT}/output/logs/digest-stderr.log
${HARDEN}
EOF

cat > "${TMP}/bitesize-digest.timer" <<EOF
[Unit]
Description=Run the BiteSIze pool every day at 06:50

[Timer]
OnCalendar=*-*-* 06:50:00
# Catch up on a run missed while the box was off.
Persistent=true
Unit=bitesize-digest.service

[Install]
WantedBy=timers.target
EOF

echo "Writing units to ${UNIT_DIR} (needs sudo)..."
sudo install -m 0644 "${TMP}"/bitesize-dashboard.service "${TMP}"/bitesize-digest.service \
  "${TMP}"/bitesize-digest.timer "${UNIT_DIR}/"
sudo systemctl daemon-reload
sudo systemctl enable --now bitesize-dashboard.service
sudo systemctl enable --now bitesize-digest.timer

echo
echo "Installed:"
echo "  bitesize-dashboard.service  http://127.0.0.1:${PORT}  (logs: output/logs/dashboard-*.log)"
echo "  bitesize-digest.timer       daily 06:50 $(timedatectl show -p Timezone --value 2>/dev/null || true)  (logs: output/logs/digest-*.log)"
echo
echo "  Status:   systemctl status bitesize-dashboard bitesize-digest.timer"
echo "  Run now:  sudo systemctl start bitesize-digest"
echo "  Remove:   sudo systemctl disable --now bitesize-dashboard bitesize-digest.timer"
echo
echo "  Publish on the tailnet: tailscale serve --bg --https=443 ${PORT}"
