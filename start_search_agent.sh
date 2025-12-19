#!/bin/bash
# Start the Search Agent Server on the remote server

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default server configuration
SERVER_HOST="${SERVER_HOST:-sf.lti.cs.cmu.edu}"
SERVER_USER="${SERVER_USER:-weiweis}"
REMOTE_PATH="${REMOTE_PATH:-/usr1/data/weiweis/chat_server}"

echo "Starting Search Agent Server on ${SERVER_HOST}..."

expect <<EOF
spawn ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_HOST} "cd ${REMOTE_PATH}/agent_service/search && export PYTHONPATH=${REMOTE_PATH}:\$PYTHONPATH && nohup /home/${SERVER_USER}/.local/bin/uvicorn server:app --host 0.0.0.0 --port 8001 > ${REMOTE_PATH}/logs/search_agent.log 2>&1 &"
expect "password:"
send "\${SSH_PASSWORD}\r"
expect eof
EOF

echo "Waiting for server to start..."
sleep 3

# Check if server is running
curl -s http://${SERVER_HOST}:8001/health | jq .

echo ""
echo "Search Agent Server started!"
echo "Health check: http://${SERVER_HOST}:8001/health"
echo "API endpoint: http://${SERVER_HOST}:8001/v1/chat/completions"
echo "Logs: ssh ${SERVER_USER}@${SERVER_HOST} 'tail -f ${REMOTE_PATH}/logs/search_agent.log'"

