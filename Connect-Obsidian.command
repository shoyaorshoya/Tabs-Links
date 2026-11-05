#!/usr/bin/env bash
# Double-click (Mac): connect ClosedTabs to your Obsidian vault. Finds your vaults automatically,
# saves the setting in deploy/.env, restarts ClosedTabs and runs the first sync.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:$PATH"
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
LABEL="com.closedtabs.app"
URL="http://localhost:3000"
msg() { printf '%s\n' "$*"; }

# Python: the one ClosedTabs installed, otherwise any Python 3
CLOSEDTABS_INSTALL_ONLY=1 bash "$ROOT/start-local.sh" >/dev/null 2>&1 || true
PY="$ROOT/app/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
if [ -z "$PY" ]; then msg "✗ Python not found. Run ClosedTabs.command once first."; exit 1; fi

msg "ClosedTabs ↔ Obsidian"
msg "─────────────────────"

# 1. find vaults (Obsidian keeps the list in obsidian.json)
VAULTS=$("$PY" - <<'PY'
import json, os
cfg = os.path.expanduser("~/Library/Application Support/obsidian/obsidian.json")
try:
    vaults = json.load(open(cfg, encoding="utf-8")).get("vaults", {})
except Exception:
    vaults = {}
items = [v for v in vaults.values() if isinstance(v, dict) and os.path.isdir(v.get("path", ""))]
items.sort(key=lambda v: (not v.get("open", False), -int(v.get("ts", 0) or 0)))
for v in items:
    print(v["path"])
PY
)

CHOSEN=""
if [ -n "$VAULTS" ]; then
  COUNT=$(printf '%s\n' "$VAULTS" | wc -l | tr -d ' ')
  if [ "$COUNT" = "1" ]; then
    CHOSEN="$VAULTS"
    msg "Found your vault:"
    msg "  $CHOSEN"
    read -r -p "Connect this one? [Y/n] " ans
    case "$ans" in n|N|no|nem) CHOSEN="";; esac
  else
    msg "Found these vaults (the one open in Obsidian is first):"
    i=1; while IFS= read -r v; do msg "  $i) $v"; i=$((i+1)); done <<< "$VAULTS"
    read -r -p "Type the number of the vault to connect (default 1): " num
    num=${num:-1}
    CHOSEN=$(printf '%s\n' "$VAULTS" | sed -n "${num}p")
  fi
fi
if [ -z "$CHOSEN" ]; then
  msg ""
  msg "Drag your vault folder into this window, then press Enter:"
  read -r CHOSEN
  CHOSEN=$(printf '%s' "$CHOSEN" | sed -e "s/^[\"']//" -e "s/[\"']$//" -e 's/\\ / /g' -e 's/[[:space:]]*$//')
fi
if [ ! -d "$CHOSEN" ]; then msg "✗ That folder doesn't exist: $CHOSEN"; exit 1; fi

# 2. save it in deploy/.env (replaces an earlier OBSIDIAN_VAULT line)
[ -f deploy/.env ] || cp deploy/.env.example deploy/.env
VAULT="$CHOSEN" "$PY" - <<'PY'
import os, re
path = "deploy/.env"
v = os.environ["VAULT"]
quoted = '"' + re.sub(r'(["$`\\])', r"\\\1", v) + '"'
text = open(path, encoding="utf-8").read()
line = f"OBSIDIAN_VAULT={quoted}"
if re.search(r"(?m)^OBSIDIAN_VAULT=.*$", text):
    text = re.sub(r"(?m)^OBSIDIAN_VAULT=.*$", lambda m: line, text)
else:
    text = text.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(text)
PY
msg "✓ Saved in deploy/.env"

# 3. restart ClosedTabs so it picks up the setting
start_here() {
  msg "→ Starting ClosedTabs in this window (keep it open)…"
  pkill -f "uvicorn closedtabs.web:app" 2>/dev/null; sleep 1
  CLOSEDTABS_BACKGROUND=1 bash "$ROOT/start-local.sh" &
  HERE_PID=$!
}
HERE_PID=""
if [ -f "$HOME/Library/LaunchAgents/$LABEL.plist" ] && command -v launchctl >/dev/null; then
  msg "→ Restarting ClosedTabs (background)…"
  launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null || true
else
  start_here
fi

up=""
for _ in $(seq 1 40); do
  if curl -fs -o /dev/null --max-time 2 "$URL/health"; then up=1; break; fi
  sleep 1
done
if [ -z "$up" ]; then msg "✗ ClosedTabs didn't start. Look at app/data/closedtabs.log"; exit 1; fi

# 4. first sync + result
sync_now() { curl -fs -o /dev/null -X POST "$URL/obsidian/sync" --max-time 120 || true; }
sync_now
STATUS=$(curl -fs "$URL/health" | "$PY" -c 'import json,sys; o=json.load(sys.stdin).get("obsidian",{}); print(o.get("error") or "OK")' 2>/dev/null)

if [ "$STATUS" != "OK" ] && [ -z "$HERE_PID" ]; then
  msg ""
  msg "⚠ macOS didn't let the background ClosedTabs write into this vault"
  msg "  (vaults in iCloud Drive, Documents or Desktop are protected)."
  read -r -p "Switch to starting ClosedTabs from this window instead? [Y/n] " ans
  case "$ans" in n|N|no|nem) ;; *)
    bash "$ROOT/Autostart-OFF.command" >/dev/null 2>&1 || true
    start_here
    for _ in $(seq 1 40); do curl -fs -o /dev/null --max-time 2 "$URL/health" && break; sleep 1; done
    sync_now
    STATUS=$(curl -fs "$URL/health" | "$PY" -c 'import json,sys; o=json.load(sys.stdin).get("obsidian",{}); print(o.get("error") or "OK")' 2>/dev/null)
    msg "  From now on, start ClosedTabs with ClosedTabs.command.";;
  esac
fi

msg ""
if [ "$STATUS" = "OK" ]; then
  msg "✓ Connected! Your library is in Obsidian, folder: ClosedTabs"
  msg "  It syncs every 30 seconds while ClosedTabs runs."
  HOME_NOTE="$CHOSEN/ClosedTabs/ClosedTabs.md"
  ENC=$("$PY" -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$HOME_NOTE")
  command -v open >/dev/null && open "obsidian://open?path=$ENC" 2>/dev/null || true
else
  msg "✗ $STATUS"
fi

if [ -n "$HERE_PID" ]; then
  msg ""
  msg "ClosedTabs keeps running while this window is open (close it or press Ctrl + C to stop)."
  wait "$HERE_PID"
fi
