#!/usr/bin/env bash
# Double-click once (Mac): ClosedTabs then starts by itself at every login and runs in the background.
# Undo with Autostart-OFF.command. Logs: app/data/closedtabs.log
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.closedtabs.app"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

msg() { printf '%s\n' "$*"; }
trap 'msg ""; msg "You can close this window."' EXIT

# Background apps may not read iCloud Drive / Desktop / Documents / Downloads (macOS privacy rules).
case "$ROOT" in
  */Library/Mobile\ Documents/*|"$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*)
    msg "✗ The ClosedTabs folder is in iCloud Drive, Desktop, Documents or Downloads:"
    msg "    $ROOT"
    msg ""
    msg "  macOS doesn't let background apps use those folders. Please:"
    msg "  1. Quit ClosedTabs if it's running (Ctrl + C in its Terminal window)."
    msg "  2. In Finder, drag the whole ClosedTabs folder into your home folder"
    msg "     (Finder menu: Go → Home). Your links move with it (they're in app/data)."
    msg "  3. Double-click Autostart-ON.command again from the new place."
    exit 1;;
esac

# Make sure everything is installed before handing it to macOS.
CLOSEDTABS_INSTALL_ONLY=1 bash "$ROOT/start-local.sh"

# Stop a copy that's running in a Terminal window, so the background one can take over port 3000.
pkill -f "uvicorn closedtabs.web:app" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

mkdir -p "$HOME/Library/LaunchAgents"
esc() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$(esc "$ROOT/start-local.sh")</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>CLOSEDTABS_BACKGROUND</key><string>1</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>StandardOutPath</key><string>$(esc "$ROOT/app/data/closedtabs.log")</string>
  <key>StandardErrorPath</key><string>$(esc "$ROOT/app/data/closedtabs.log")</string>
</dict>
</plist>
EOF
mkdir -p "$ROOT/app/data"
launchctl bootstrap "gui/$(id -u)" "$PLIST"

printf "→ Starting"
for _ in $(seq 1 30); do
  if curl -fs -o /dev/null --max-time 2 http://localhost:3000/health; then
    msg ""; msg "✓ Done! ClosedTabs now runs in the background and starts by itself when you log in."
    msg "  Open it any time: http://localhost:3000  (tip: bookmark it)"
    open http://localhost:3000 || true
    exit 0
  fi
  printf '.'; sleep 2
done
msg ""; msg "✗ It didn't start. The details are in: $ROOT/app/data/closedtabs.log"
msg "  Send me the last lines of that file and I'll help."
exit 1
