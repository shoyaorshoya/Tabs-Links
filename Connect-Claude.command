#!/usr/bin/env bash
# Double-click (Mac): let the Claude desktop app (and Claude Code, if installed) use your ClosedTabs library.
# Adds a "closedtabs" entry to Claude's config (a backup of the old config is kept), nothing else changes.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.volta/bin:$HOME/.nvm/versions/node/current/bin:$PATH"
ROOT="$(cd "$(dirname "$0")" && pwd)"
URL="http://localhost:3000"
CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
BRIDGE="mcp-remote@0.16.0"
msg() { printf '%s\n' "$*"; }

msg "ClosedTabs → Claude"
msg "───────────────────"

# 0. ClosedTabs should be running (Claude talks to it at $URL/mcp)
if ! curl -fs -o /dev/null --max-time 3 "$URL/health"; then
  msg "⚠ ClosedTabs isn't running right now. That's OK for the setup, but Claude can only use your"
  msg "  library while it runs (autostart, or ClosedTabs.command)."
fi

# 1. Node.js is needed for the small bridge between the Claude app and ClosedTabs
NPX="$(command -v npx || true)"
if [ -z "$NPX" ]; then
  msg "✗ Node.js isn't installed. Claude needs it to reach ClosedTabs."
  msg "  1. Install the LTS version from https://nodejs.org (opening it now)"
  msg "  2. Then double-click Connect-Claude.command again."
  command -v open >/dev/null && open "https://nodejs.org/en/download" || true
  exit 1
fi
NODE_DIR="$(dirname "$(command -v node)")"
msg "✓ Node.js found ($NODE_DIR)"

PY="$ROOT/app/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"

# 2. Claude desktop app: add the closedtabs server to its config (keeps everything else)
mkdir -p "$(dirname "$CONFIG")"
RESULT=$(CONFIG="$CONFIG" NPX="$NPX" NODE_DIR="$NODE_DIR" BRIDGE="$BRIDGE" URL="$URL" "$PY" - <<'PY'
import json, os, shutil, time
cfg = os.environ["CONFIG"]
data = {}
if os.path.exists(cfg) and open(cfg, encoding="utf-8").read().strip():
    try:
        data = json.load(open(cfg, encoding="utf-8"))
    except ValueError:
        print("BADJSON"); raise SystemExit
    shutil.copy2(cfg, f"{cfg}.backup-{time.strftime('%Y%m%d-%H%M%S')}")
servers = data.setdefault("mcpServers", {})
entry = {
    "command": os.environ["NPX"],
    "args": ["-y", os.environ["BRIDGE"], os.environ["URL"] + "/mcp", "--allow-http"],
    "env": {"PATH": f"{os.environ['NODE_DIR']}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"},
}
state = "same" if servers.get("closedtabs") == entry else ("updated" if "closedtabs" in servers else "added")
servers["closedtabs"] = entry
json.dump(data, open(cfg, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(state)
PY
)
case "$RESULT" in
  BADJSON) msg "✗ Claude's config file isn't valid JSON, so I didn't touch it:"; msg "  $CONFIG"; exit 1;;
  added|updated|same) msg "✓ Claude desktop app: closedtabs connector $RESULT";;
  *) msg "✗ Couldn't update Claude's config: $RESULT"; exit 1;;
esac

# 3. Download the bridge once now, so Claude's first start doesn't time out
msg "→ Preparing the bridge (one time)…"
"$NPX" -y "$BRIDGE" "$URL/mcp" --allow-http </dev/null >/dev/null 2>&1 &
BPID=$!; sleep 25; kill "$BPID" 2>/dev/null; wait "$BPID" 2>/dev/null

# 4. Claude Code (terminal), if installed
if command -v claude >/dev/null; then
  if claude mcp get closedtabs >/dev/null 2>&1; then
    msg "✓ Claude Code: closedtabs already connected"
  elif claude mcp add --scope user --transport http closedtabs "$URL/mcp" >/dev/null 2>&1; then
    msg "✓ Claude Code: closedtabs connected"
  else
    msg "  Claude Code: run this yourself: claude mcp add --scope user --transport http closedtabs $URL/mcp"
  fi
fi

# 5. Restart the Claude app so it loads the connector
msg ""
if pgrep -xq Claude 2>/dev/null; then
  read -r -p "Restart the Claude app now to load it? [Y/n] " ans
  case "$ans" in n|N|no|nem) msg "OK. Quit Claude completely (Cmd + Q) and open it again later.";;
    *) osascript -e 'quit app "Claude"' >/dev/null 2>&1; sleep 3; open -a Claude 2>/dev/null; msg "✓ Claude restarted";;
  esac
else
  msg "Open the Claude app: 'closedtabs' appears under the tools/connectors (+) menu."
fi
msg ""
msg "Try asking Claude: “What did I save about onboarding? Give me the 5 best with links.”"
