#!/usr/bin/env bash
set -euo pipefail
# Start all agents: sources root .env then per-agent .env and launches uvicorn

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f ".venv/bin/activate" ]; then
  # Activate local virtualenv if present
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

mkdir -p logs
PIDS_FILE="$ROOT_DIR/.agent_pids"
rm -f "$PIDS_FILE"

start_agent() {
  AGENT_MODULE=$1
  AGENT_DIR=$2
  AGENT_NAME=$3
  echo "Starting $AGENT_NAME..."
  (
    # Load repo-level env then agent-local env
    [ -f "$ROOT_DIR/.env" ] && set -a && . "$ROOT_DIR/.env" && set +a
    if [ -f "$ROOT_DIR/$AGENT_DIR/.env" ]; then
      set -a
      . "$ROOT_DIR/$AGENT_DIR/.env"
      set +a
    fi

    # Default host
    HOST=${HOST:-127.0.0.1}
    # Default port fallback per agent if PORT not set
    case "$AGENT_NAME" in
      triage) DEFAULT_PORT=8003 ;; 
      pediatria) DEFAULT_PORT=8004 ;;
      clinica_general) DEFAULT_PORT=8005 ;;
      oncologia) DEFAULT_PORT=8006 ;;
      booking_mcp) DEFAULT_PORT=8010 ;;
      main_agent) DEFAULT_PORT=8310 ;;
      *) DEFAULT_PORT=8000 ;;
    esac

    PORT=${PORT:-$DEFAULT_PORT}
    export HOST="0.0.0.0"
    export AGENT_URL="http://host.docker.internal:$PORT"
    export PUBLIC_URL="http://host.docker.internal:$PORT"
    export MAIN_AGENT_URL="http://host.docker.internal:8310"


    # Launch uvicorn in background, log to logs/
    nohup uvicorn "$AGENT_MODULE:app" --host "$HOST" --port "$PORT" --log-level info >> "logs/$AGENT_NAME.log" 2>&1 &
    echo $! >> "$PIDS_FILE"
    echo "$AGENT_NAME started on $HOST:$PORT (logs/$AGENT_NAME.log)"
  )
}

start_agent src.agents.triage.triage src/agents/triage triage
start_agent src.agents.pediatria.pediatria src/agents/pediatria pediatria
start_agent src.agents.clinica_general.clinica_general src/agents/clinica_general clinica_general
start_agent src.agents.oncologia.oncologia src/agents/oncologia oncologia
start_agent src.agents.booking_mcp.booking_mcp src/agents/booking_mcp booking_mcp
start_agent src.agents.main_agent.main_agent src/agents/main_agent main_agent


echo "All agents started. PIDs recorded in $PIDS_FILE"
echo "Tails of logs (last 5 lines each):"
tail -n 5 logs/*.log || true
