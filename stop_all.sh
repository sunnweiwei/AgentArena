#!/bin/bash
# Stop all AgentArena services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🛑 Stopping AgentArena Services..."
echo ""

# Stop services by PID if files exist
if [ -f "logs/backend.pid" ]; then
    PID=$(cat logs/backend.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Stopped Backend (PID: $PID)"
    fi
fi

if [ -f "logs/agent_service.pid" ]; then
    PID=$(cat logs/agent_service.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Stopped Agent Service (PID: $PID)"
    fi
fi

if [ -f "logs/runtime_service.pid" ]; then
    PID=$(cat logs/runtime_service.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Stopped Runtime Service (PID: $PID)"
    fi
fi

if [ -f "logs/frontend.pid" ]; then
    PID=$(cat logs/frontend.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Stopped Frontend (PID: $PID)"
    fi
fi

# Also kill by process name as fallback
pkill -f "python.*main.py" 2>/dev/null && echo -e "${GREEN}✓${NC} Stopped any remaining backend processes" || true
pkill -f "python.*agent_main" 2>/dev/null && echo -e "${GREEN}✓${NC} Stopped any remaining agent service processes" || true
pkill -f "python.*runtime_server" 2>/dev/null && echo -e "${GREEN}✓${NC} Stopped any remaining runtime service processes" || true
pkill -f "vite" 2>/dev/null && echo -e "${GREEN}✓${NC} Stopped any remaining frontend processes" || true

# Clean up PID files
rm -f logs/*.pid 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ All services stopped${NC}"

