#!/bin/bash

# Keep-alive script - runs backend in a loop with auto-restart
# This ensures the backend stays running even if it crashes

BACKEND_DIR="/usr1/data/weiweis/chat_server/backend"
LOG_DIR="/usr1/data/weiweis/chat_server/logs"
MAX_RESTARTS=10
RESTART_DELAY=5

mkdir -p "$LOG_DIR"

cd "$BACKEND_DIR"
source venv/bin/activate

restart_count=0

while [ $restart_count -lt $MAX_RESTARTS ]; do
    echo "$(date): Starting backend (attempt $((restart_count + 1)))" >> "$LOG_DIR/keep_alive.log"
    
    # Start backend
    python main.py >> "$LOG_DIR/backend.log" 2>&1
    
    exit_code=$?
    restart_count=$((restart_count + 1))
    
    if [ $exit_code -eq 0 ]; then
        echo "$(date): Backend exited normally" >> "$LOG_DIR/keep_alive.log"
        break
    else
        echo "$(date): Backend crashed with exit code $exit_code, restarting in $RESTART_DELAY seconds..." >> "$LOG_DIR/keep_alive.log"
        sleep $RESTART_DELAY
    fi
done

if [ $restart_count -ge $MAX_RESTARTS ]; then
    echo "$(date): Maximum restart attempts reached, stopping" >> "$LOG_DIR/keep_alive.log"
fi



