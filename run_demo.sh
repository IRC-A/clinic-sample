#!/usr/bin/env bash
# Helper script to run demo with automatic .venv activation
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "⚠️ Virtual environment not found in .venv or venv."
    echo "Creating .venv and installing required packages..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install google-adk google-genai pytest-asyncio
fi

echo "============================================================"
echo "🚀 Executing Google All Things Agentic Hackathon Demo..."
echo "============================================================"
PYTHONPATH=. python3 demo_hackathon.py
