#!/usr/bin/env bash
# Double-click (Mac): stop ClosedTabs running in the background and don't start it at login any more.
# Your links are NOT deleted. Start it again with ClosedTabs.command or Autostart-ON.command.
LABEL="com.closedtabs.app"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
pkill -f "uvicorn closedtabs.web:app" 2>/dev/null || true
echo "✓ Autostart is off and ClosedTabs is stopped. Your links are safe in app/data."
echo ""
echo "You can close this window."
