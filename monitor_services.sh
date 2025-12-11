#!/bin/bash

# Service monitor script - checks and restarts services if they fail
# Run this periodically via cron: */5 * * * * /usr1/data/weiweis/chat_server/monitor_services.sh

BACKEND_DIR="/usr1/data/weiweis/chat_server/backend"
FRONTEND_DIR="/usr1/data/weiweis/chat_server/frontend"
LOG_DIR="/usr1/data/weiweis/chat_server/logs"

mkdir -p "$LOG_DIR"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_DIR/monitor.log"
}

# Check backend process
if ! pgrep -f "python.*main.py" > /dev/null; then
    log_message "Backend process not running, restarting..."
    cd "$BACKEND_DIR"
    source venv/bin/activate
    nohup python main.py > "$LOG_DIR/backend.log" 2>&1 &
    sleep 3
fi

# Check if backend is responding (health check)
if ! curl -s --max-time 3 http://localhost:8000/health > /dev/null 2>&1; then
    log_message "Backend not responding to health check, restarting..."
    pkill -f "python.*main.py" 2>/dev/null
    sleep 2
    cd "$BACKEND_DIR"
    source venv/bin/activate
    nohup python main.py > "$LOG_DIR/backend.log" 2>&1 &
    sleep 3
    
    # Verify it's working
    if curl -s --max-time 3 http://localhost:8000/health > /dev/null 2>&1; then
        log_message "Backend restarted successfully"
    else
        log_message "ERROR: Backend restart failed - check logs"
    fi
fi

# Check frontend process
if ! pgrep -f "node.*vite" > /dev/null; then
    log_message "Frontend process not running, restarting..."
    cd "$FRONTEND_DIR"
    source ~/.nvm/nvm.sh 2>/dev/null || true
    nohup bash -c 'source ~/.nvm/nvm.sh && npm run dev' > "$LOG_DIR/frontend.log" 2>&1 &
    sleep 5
fi

# Check if frontend is responding
if ! curl -s --max-time 3 http://localhost:3000/ > /dev/null 2>&1; then
    log_message "Frontend not responding, restarting..."
    pkill -f "node.*vite" 2>/dev/null
    sleep 2
    cd "$FRONTEND_DIR"
    source ~/.nvm/nvm.sh 2>/dev/null || true
    nohup bash -c 'source ~/.nvm/nvm.sh && npm run dev' > "$LOG_DIR/frontend.log" 2>&1 &
    sleep 5
    
    # Verify it's working
    if curl -s --max-time 3 http://localhost:3000/ > /dev/null 2>&1; then
        log_message "Frontend restarted successfully"
    else
        log_message "ERROR: Frontend restart failed - check logs"
    fi
fi

