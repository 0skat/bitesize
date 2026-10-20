#!/usr/bin/env bash
# Install a macOS LaunchAgent that runs BiteSIze every day at 6:50 AM (local time).
# Requires a project virtualenv at .venv with dependencies installed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.bitesize.digest"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
VENV_PY="${ROOT}/.venv/bin/python"

if [[ ! -x "${VENV_PY}" ]]; then
  echo "error: expected Python at ${VENV_PY}" >&2
  echo "  Create it with: cd \"${ROOT}\" && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents" "${ROOT}/output/logs"

cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <!-- caffeinate -i holds off idle sleep for as long as the digest runs. A
       laptop that sleeps mid-run leaves the job parked at 0% CPU with its
       network calls timing out, resuming only when someone touches the
       machine. This does not wake a Mac that is already asleep at 06:50 -
       see the pmset note this script prints. -->
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string>
    <string>-i</string>
    <string>${VENV_PY}</string>
    <string>${ROOT}/main.py</string>
    <string>--all</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>50</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${ROOT}/output/logs/digest-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/output/logs/digest-stderr.log</string>
</dict>
</plist>
EOF

launchctl unload "${PLIST}" 2>/dev/null || true
launchctl load -w "${PLIST}"

echo "Installed ${PLIST}"
echo "  Runs daily at 6:50 AM: caffeinate -i ${VENV_PY} ${ROOT}/main.py --all"
echo "  Delivers EPUB to Kindle (if configured) and copies to iCloud Books for iPhone sync"
echo "  Logs: ${ROOT}/output/logs/digest-stdout.log (and digest-stderr.log)"
echo "  Uninstall: launchctl unload \"${PLIST}\" && rm \"${PLIST}\""
echo
echo "  NOTE: launchd cannot run this on a sleeping Mac. caffeinate keeps the"
echo "  machine awake once the job has started, but something has to wake it"
echo "  first. Schedule that yourself (needs sudo, asks for your password):"
echo
echo "      sudo pmset repeat wakeorpoweron MTWRFSU 06:45:00"
echo
echo "  Check with 'pmset -g sched'; clear with 'sudo pmset repeat cancel'."
echo "  Without it, a missed run starts whenever the Mac next wakes."
