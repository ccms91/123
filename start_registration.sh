#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  Station 1 – Registration  (Linux / macOS)
#  Run:  bash start_registration.sh
# ──────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "[ERROR] Virtual environment not found."
    echo "        Run:  python3 -m venv .venv && pip install -r requirements.txt"
    exit 1
fi

# Start MRZ watcher in background
python local/mrz_watcher.py &
MRZ_PID=$!
echo "[start] MRZ watcher started (PID $MRZ_PID)"

# Open browser after a short delay
(sleep 2 && python -c "import webbrowser; webbrowser.open('http://localhost:5100/register')") &

# Start Flask app (foreground)
echo "[start] Registration app starting at http://localhost:5100"
python local/registration_app.py

# On exit, kill the watcher
kill "$MRZ_PID" 2>/dev/null || true
