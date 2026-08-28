#!/usr/bin/env bash
# NOTE: no `set -e` — cleanup steps (pkill/rm) legitimately "fail" when there is
# nothing to clean, and that must not abort the script.

# preflight.sh — org-scrape skill pre-flight cleanup
# Runs before any scraping session to ensure a clean agent-browser environment.
#
# Steps:
#   1. Close all active agent-browser sessions gracefully
#   2. FORCE-kill any lingering agent-browser daemons + purge ALL session files.
#      (Graceful close leaves "alive but wedged" daemons that accept no new session
#      and block every subsequent `open` with "Daemon failed to start" — the chronic
#      failure this step fixes. Only the main thread runs this; subagents never do.)
#   3. Delete all /tmp/ab-* temp profiles from previous scrape runs

echo "=== org-scrape Pre-flight Cleanup ==="

# 1. Graceful close first (lets healthy daemons shut down cleanly)
echo "[1/3] Closing all active agent-browser sessions..."
if command -v agent-browser &>/dev/null; then
  agent-browser close --all >/dev/null 2>&1 || true
  echo "  Done."
else
  echo "  Skipped (agent-browser not found on PATH)."
fi

# 2. Force-kill wedged daemons, then purge ALL session state (not just dead PIDs).
echo "[2/3] Force-clearing daemons and session files..."
session_dir="$HOME/.agent-browser"
# The daemon processes are `node .../agent-browser/.../daemon.js`. Match both tokens
# so we never touch an unrelated daemon.js from another tool.
killed=$(pgrep -f "agent-browser.*daemon.js" 2>/dev/null | wc -l | tr -d ' ')
pkill -9 -f "agent-browser.*daemon.js" 2>/dev/null || true
# Give the OS a moment to release the sockets before they're recreated.
sleep 1 2>/dev/null || true
# Purge every session artifact so the next `open` starts a fresh daemon.
if [ -d "$session_dir" ]; then
  rm -f "$session_dir"/*.pid "$session_dir"/*.sock "$session_dir"/*.engine 2>/dev/null || true
fi
echo "  Killed $killed daemon(s); session files purged."

# 3. Clean all /tmp/ab-* temp profiles from previous scrape runs
echo "[3/3] Cleaning temp profiles..."
removed=0
for dir in /tmp/ab-*; do
  if [ -d "$dir" ]; then
    rm -rf "$dir" 2>/dev/null || true
    removed=$((removed + 1))
  fi
done
echo "  Removed $removed temp profile(s)."

echo "=== Pre-flight cleanup complete ==="
