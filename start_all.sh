#!/bin/bash
# Start all services for AgentArena using uv

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🚀 Starting AgentArena Services..."
echo ""

# Function to check if a port is in use
check_port() {
    lsof -i :$1 > /dev/null 2>&1
    return $?
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} $name is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo -e "${YELLOW}⚠${NC} $name may not be ready yet (timeout after ${max_attempts}s)"
    return 1
}

# Check if ports are available
PORTS_IN_USE=false
if check_port 8000; then
    echo -e "${YELLOW}⚠${NC}  Port 8000 (Backend) is already in use"
    PORTS_IN_USE=true
fi

if check_port 8001; then
    echo -e "${YELLOW}⚠${NC}  Port 8001 (Agent Service) is already in use"
    PORTS_IN_USE=true
fi

if check_port 8005; then
    echo -e "${YELLOW}⚠${NC}  Port 8005 (Runtime Service) is already in use"
    PORTS_IN_USE=true
fi

if check_port 3000; then
    echo -e "${YELLOW}⚠${NC}  Port 3000 (Frontend) is already in use"
    PORTS_IN_USE=true
fi

if [ "$PORTS_IN_USE" = true ]; then
    echo ""
    read -p "Some ports are in use. Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo ""
echo "Starting services..."
echo ""

# Check if .env files exist
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}⚠${NC}  Warning: backend/.env not found. Backend may not work correctly."
fi

if [ ! -f "agent_service/.env" ]; then
    echo -e "${YELLOW}⚠${NC}  Warning: agent_service/.env not found. Agent service may not work correctly."
fi

if [ ! -f "runtime_service/.env" ]; then
    echo -e "${YELLOW}⚠${NC}  Warning: runtime_service/.env not found. Runtime service may not work correctly."
fi

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"

# Start Backend (port 8000)
echo "1. Starting Backend (port 8000)..."
cd "$SCRIPT_DIR/backend"
if [ -f ".env" ]; then
    uv run --env-file=.env python main.py > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
else
    uv run python main.py > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
fi
BACKEND_PID=$!
cd "$SCRIPT_DIR"
echo "   Backend PID: $BACKEND_PID"

# Start Agent Service (port 8001)
echo "2. Starting Agent Service (port 8001)..."
cd "$SCRIPT_DIR/agent_service"
if [ -f ".env" ]; then
    uv run --env-file=.env python agent_main.py > "$SCRIPT_DIR/logs/agent_service.log" 2>&1 &
else
    uv run python agent_main.py > "$SCRIPT_DIR/logs/agent_service.log" 2>&1 &
fi
AGENT_PID=$!
cd "$SCRIPT_DIR"
echo "   Agent Service PID: $AGENT_PID"

# Start Runtime Service (port 8005)
echo "3. Starting Runtime Service (port 8005)..."
cd "$SCRIPT_DIR/runtime_service"
if [ -f ".env" ]; then
    uv run --env-file=.env python runtime_server.py > "$SCRIPT_DIR/logs/runtime_service.log" 2>&1 &
else
    uv run python runtime_server.py > "$SCRIPT_DIR/logs/runtime_service.log" 2>&1 &
fi
RUNTIME_PID=$!
cd "$SCRIPT_DIR"
echo "   Runtime Service PID: $RUNTIME_PID"

# Start Frontend (port 3000)
echo "4. Starting Frontend (port 3000)..."
cd "$SCRIPT_DIR/frontend"
npm run dev > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"
echo "   Frontend PID: $FRONTEND_PID"

# Save PIDs to file for easy stopping
echo "$BACKEND_PID" > "$SCRIPT_DIR/logs/backend.pid"
echo "$AGENT_PID" > "$SCRIPT_DIR/logs/agent_service.pid"
echo "$RUNTIME_PID" > "$SCRIPT_DIR/logs/runtime_service.pid"
echo "$FRONTEND_PID" > "$SCRIPT_DIR/logs/frontend.pid"

echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Check service health
echo ""
echo "Checking service health..."
wait_for_service "http://localhost:8000/health" "Backend"
wait_for_service "http://localhost:8001/health" "Agent Service"
wait_for_service "http://localhost:8005/health" "Runtime Service"
wait_for_service "http://localhost:3000" "Frontend"

echo ""
echo -e "${GREEN}✅ All services started!${NC}"
echo ""
echo "Service URLs:"
echo "  - Frontend:    http://localhost:3000"
echo "  - Backend:     http://localhost:8000"
echo "  - Agent:       http://localhost:8001"
echo "  - Runtime:     http://localhost:8005"
echo ""
echo "Logs are in: $SCRIPT_DIR/logs/"
echo "  - backend.log"
echo "  - agent_service.log"
echo "  - runtime_service.log"
echo "  - frontend.log"
echo ""
echo "To stop all services, run: ./stop_all.sh"
echo "Or manually: pkill -f 'python.*main.py|python.*agent_main|python.*runtime_server|vite'"


