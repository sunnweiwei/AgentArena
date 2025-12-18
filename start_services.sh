#!/bin/bash

# Robust service startup script with auto-restart
# This script ensures services stay running

BACKEND_DIR="/usr1/data/weiweis/chat_server/backend"
FRONTEND_DIR="/usr1/data/weiweis/chat_server/frontend"
LOG_DIR="/usr1/data/weiweis/chat_server/logs"

# Create log directory
mkdir -p "$LOG_DIR"

# Ensure HTTPS is enabled for the frontend unless explicitly disabled
: "${ENABLE_HTTPS:=true}"
export ENABLE_HTTPS

: "${TRANSCRIPTION_MODEL:=gpt-4o-mini-transcribe}"
export TRANSCRIPTION_MODEL

# Function to check if a process is running
is_running() {
    local pattern=$1
    pgrep -f "$pattern" > /dev/null
}

# Function to start backend
start_backend() {
    if is_running "python.*main.py"; then
        echo "Backend is already running"
        return 0
    fi
    
    echo "Starting backend..."
    cd "$BACKEND_DIR"
    # Kill any stale processes first
    pkill -f "python.*main.py" 2>/dev/null || true
    sleep 1
    
    # Start with proper environment
    source venv/bin/activate
    nohup python main.py > "$LOG_DIR/backend.log" 2>&1 &
    sleep 3
    
    # Verify it's running and responding
    if is_running "python.*main.py"; then
        # Wait a bit more and test health endpoint
        sleep 2
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "Backend started successfully and is healthy"
            return 0
        else
            echo "Backend process started but not responding - check logs"
            return 1
        fi
    else
        echo "Failed to start backend - check logs at $LOG_DIR/backend.log"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    if is_running "node.*vite"; then
        echo "Frontend is already running"
        return 0
    fi
    
    echo "Starting frontend..."
    cd "$FRONTEND_DIR"
    # Source nvm to get npm
    source ~/.nvm/nvm.sh 2>/dev/null || true
    nohup bash -c 'export ENABLE_HTTPS=\$ENABLE_HTTPS && source ~/.nvm/nvm.sh && npm run dev' > "$LOG_DIR/frontend.log" 2>&1 &
    sleep 5
    
    if is_running "node.*vite"; then
        echo "Frontend started successfully"
        return 0
    else
        echo "Failed to start frontend"
        return 1
    fi
}

# Function to check health
check_health() {
    local service=$1
    if [ "$service" == "backend" ]; then
        curl -s http://localhost:8000/health > /dev/null 2>&1
        return $?
    elif [ "$service" == "frontend" ]; then
        curl -s http://localhost:3000/ > /dev/null 2>&1
        return $?
    fi
    return 1
}

# Main function
main() {
    echo "=== Starting Chat Server Services ==="
    echo "Time: $(date)"
    
    # Start backend
    if ! start_backend; then
        echo "ERROR: Failed to start backend"
        exit 1
    fi
    
    # Start frontend
    if ! start_frontend; then
        echo "ERROR: Failed to start frontend"
        exit 1
    fi
    
    # Wait and verify
    sleep 3
    
    if check_health "backend"; then
        echo "✓ Backend is healthy"
    else
        echo "⚠ Backend health check failed"
    fi
    
    if check_health "frontend"; then
        echo "✓ Frontend is healthy"
    else
        echo "⚠ Frontend health check failed"
    fi
    
    echo ""
    echo "Services started. Logs are in: $LOG_DIR"
    echo "Backend: http://localhost:8000"
    echo "Frontend: http://localhost:3000"
}

# Run main function
main

