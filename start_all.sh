#!/bin/bash
# Start all services for the chat application with search agent

echo "Starting all services..."
echo ""

# Function to check if a port is in use
check_port() {
    lsof -i :$1 > /dev/null 2>&1
    return $?
}

# Check if ports are available
if check_port 8001; then
    echo "⚠️  Warning: Port 8001 (Search Agent) is already in use"
fi

if check_port 8000; then
    echo "⚠️  Warning: Port 8000 (Backend) is already in use"
fi

if check_port 3000; then
    echo "⚠️  Warning: Port 3000 (Frontend) is already in use"
fi

echo ""
echo "Starting services in separate terminals..."
echo ""

# Start search agent server
echo "1. Starting Search Agent Server (Port 8001)..."
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'/agent_service/search\" && echo \"Starting Search Agent Server...\" && python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload"'

sleep 2

# Start backend server
echo "2. Starting Backend Server (Port 8000)..."
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'/backend\" && echo \"Starting Backend Server...\" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"'

sleep 2

# Start frontend
echo "3. Starting Frontend (Port 3000)..."
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'/frontend\" && echo \"Starting Frontend...\" && npm run dev"'

echo ""
echo "✅ All services started!"
echo ""
echo "Services:"
echo "  - Search Agent Server: http://localhost:8001"
echo "  - Backend Server: http://localhost:8000"
echo "  - Frontend: http://localhost:3000"
echo ""
echo "Check the new terminal windows for logs."
echo "To use Search Agent: Select 'Search Agent' from the model dropdown in the chat interface."

