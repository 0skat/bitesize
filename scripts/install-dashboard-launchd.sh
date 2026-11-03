#!/usr/bin/env bash
# Install a macOS LaunchAgent that keeps the BiteSIze dashboard running.
#
# The dashboard is what makes the tailnet URL work: `tailscale serve` only
# proxies to 127.0.0.1:8765, so if nothing is listening there the URL is dead.
# A hand-started `./run.sh dashboard` dies with its terminal, which is no good
# when the point is to reach it from an iPad. This agent starts it at login and
# restarts it whenever it exits.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.bitesize.dashboard"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
VENV_PY="${ROOT}/.venv/bin/python"

if [[ ! -x "${VENV_PY}" ]]; then
  echo "error: expected Python at ${VENV_PY}" >&2
  echo "  Create it with: cd \"${ROOT}\" && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# The port is a constant in dashboard.py, not a setting. Read it from there
# so the messages below cannot drift away from what actually gets served.
PORT="$(sed -n 's/^PORT *= *\([0-9]\{1,\}\).*/\1/p' "${ROOT}/dashboard.py" | head -1)"
PORT="${PORT:-8765}"

mkdir -p "${HOME}/Library/LaunchAgents" "${ROOT}/output/logs"

# A second listener on the port would crash-loop under KeepAlive, so clear any
# dashboard already running - including one started by hand in a terminal.
if pgrep -f "${ROOT}/dashboard.py" >/dev/null 2>&1; then
  echo "Stopping the dashboard that is already running..."
  pkill -f "${ROOT}/dashboard.py" || true
  for _ in 1 2 3 4 5; do
    pgrep -f "${ROOT}/dashboard.py" >/dev/null 2>&1 || break
    sleep 1
  done
fi

cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${VENV_PY}</string>
    <string>${ROOT}/dashboard.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <!-- A long-lived server, so restart it however it exits. -->
  <key>KeepAlive</key>
  <true/>
  <!-- If it cannot bind the port it will exit immediately; without a throttle
       launchd would respawn it every second and fill the log. -->
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>${ROOT}/output/logs/dashboard-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/output/logs/dashboard-stderr.log</string>
</dict>
</plist>
EOF

launchctl unload "${PLIST}" 2>/dev/null || true
launchctl load -w "${PLIST}"

echo "Installed ${PLIST}"
echo "  Starts at login and restarts on exit: ${VENV_PY} ${ROOT}/dashboard.py"
echo "  Local:  http://127.0.0.1:${PORT}"
echo "  Logs:   ${ROOT}/output/logs/dashboard-stdout.log (and -stderr.log)"
echo "  Stop:   launchctl unload \"${PLIST}\""
echo "  Remove: launchctl unload \"${PLIST}\" && rm \"${PLIST}\""
echo
echo "  Do not also run './run.sh dashboard' - the port is taken and the agent"
echo "  would crash-loop against it. 'launchctl unload' first if you want to."
echo
echo "  To reach it from another device, put a tunnel in front of loopback:"
echo
echo "      tailscale serve --bg ${PORT}"
echo
echo "  Set a dashboard password before you do ('./run.sh set-password'), or"
echo "  anyone on your tailnet can read your settings. The tunnel and this"
echo "  agent both survive a reboot; the Mac still has to be awake to answer."
