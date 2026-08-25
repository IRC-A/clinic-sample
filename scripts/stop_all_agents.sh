#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PIDS_FILE="$ROOT_DIR/.agent_pids"
if [ ! -f "$PIDS_FILE" ]; then
  echo "No PIDs file found ($PIDS_FILE). Nothing to stop."
  exit 0
fi

echo "Stopping agents listed in $PIDS_FILE..."
while read -r pid; do
  if [ -z "$pid" ]; then
    continue
  fi
  if kill -0 "$pid" 2>/dev/null; then
    echo "Killing PID $pid"
    kill "$pid" || true
    sleep 0.2
  else
    echo "PID $pid not running"
  fi
done < "$PIDS_FILE"

rm -f "$PIDS_FILE"
echo "Stopped agents."
