#!/usr/bin/env bash
# Double-click to open ClosedTabs (Mac). Starts it if it isn't running yet.
cd "$(dirname "$0")" || exit 1
exec bash ./start-local.sh
